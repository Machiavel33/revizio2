//! Chunker + spool durable pour le transport résilient.
//!
//! Le chunker accumule le PCM (f32 mono 16 kHz) en trames de 4000 échantillons,
//! regroupées en fragments de 40 trames (10 s). Chaque fragment produit un
//! `ChunkOut` prêt à envoyer (trames encodées + message chunk_end + SHA-256).
//!
//! Le spool écrit chaque fragment sur disque avant envoi ; il n'est effacé
//! qu'après ACK du serveur. Après un crash ou une coupure, les fragments non
//! acquittés sont relus et réémis (idempotence garantie par chunk_seq côté serveur).

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use parking_lot::Mutex;
use uuid::Uuid;

use crate::protocol::{
    chunk_end_json, encode_frame, f32_to_pcm16, pcm_sha256, FRAMES_PER_CHUNK, FRAME_SAMPLES,
};

/// Un fragment prêt à envoyer.
#[derive(Debug, Clone)]
pub struct ChunkOut {
    pub chunk_seq: u64,
    pub frames: Vec<Vec<u8>>, // trames binaires encodées
    pub chunk_end: String,    // message JSON chunk_end
    pub sha256: String,
}

/// Accumule le PCM et produit des fragments de 10 s.
pub struct Chunker {
    session_id: Uuid,
    frame_acc: Vec<f32>,
    chunk_frames: Vec<Vec<u8>>,
    chunk_pcm: Vec<u8>,
    next_frame_seq: u64,
    next_chunk_seq: u64,
}

impl Chunker {
    pub fn new(session_id: Uuid) -> Self {
        Self {
            session_id,
            frame_acc: Vec::with_capacity(FRAME_SAMPLES),
            chunk_frames: Vec::with_capacity(FRAMES_PER_CHUNK),
            chunk_pcm: Vec::with_capacity(FRAME_SAMPLES * FRAMES_PER_CHUNK * 2),
            next_frame_seq: 0,
            next_chunk_seq: 0,
        }
    }

    /// Ajoute des échantillons f32. Retourne les fragments complets produits.
    pub fn push(&mut self, samples: &[f32]) -> Vec<ChunkOut> {
        let mut out = Vec::new();
        for &s in samples {
            self.frame_acc.push(s);
            if self.frame_acc.len() == FRAME_SAMPLES {
                self.flush_frame(&mut out);
            }
        }
        out
    }

    fn flush_frame(&mut self, out: &mut Vec<ChunkOut>) {
        let pcm = f32_to_pcm16(&self.frame_acc);
        self.frame_acc.clear();
        let frame = encode_frame(self.session_id, self.next_frame_seq, &pcm);
        self.chunk_frames.push(frame);
        self.chunk_pcm.extend_from_slice(&pcm);
        self.next_frame_seq += 1;

        if self.chunk_frames.len() == FRAMES_PER_CHUNK {
            let sha = pcm_sha256(&self.chunk_pcm);
            let sample_count = self.chunk_pcm.len() / 2;
            let chunk_end = chunk_end_json(
                self.next_chunk_seq,
                FRAMES_PER_CHUNK,
                sample_count,
                &sha,
            );
            out.push(ChunkOut {
                chunk_seq: self.next_chunk_seq,
                frames: std::mem::take(&mut self.chunk_frames),
                chunk_end,
                sha256: sha,
            });
            self.chunk_pcm.clear();
            self.next_chunk_seq += 1;
        }
    }

    /// Vide le reste (dernier fragment partiel) à l'arrêt.
    pub fn finish(&mut self) -> Option<ChunkOut> {
        // Trame partielle restante
        if !self.frame_acc.is_empty() {
            let pcm = f32_to_pcm16(&self.frame_acc);
            self.frame_acc.clear();
            let frame = encode_frame(self.session_id, self.next_frame_seq, &pcm);
            self.chunk_frames.push(frame);
            self.chunk_pcm.extend_from_slice(&pcm);
            self.next_frame_seq += 1;
        }
        if self.chunk_frames.is_empty() {
            return None;
        }
        let sha = pcm_sha256(&self.chunk_pcm);
        let sample_count = self.chunk_pcm.len() / 2;
        let frame_count = self.chunk_frames.len();
        let chunk_end = chunk_end_json(self.next_chunk_seq, frame_count, sample_count, &sha);
        let out = ChunkOut {
            chunk_seq: self.next_chunk_seq,
            frames: std::mem::take(&mut self.chunk_frames),
            chunk_end,
            sha256: sha,
        };
        self.chunk_pcm.clear();
        self.next_chunk_seq += 1;
        Some(out)
    }
}

/// Spool durable : écrit chaque fragment sur disque avant envoi, effacé après ACK.
pub struct Spool {
    dir: PathBuf,
    inner: Mutex<()>,
}

impl Spool {
    pub fn new(root: &Path, session_id: Uuid) -> std::io::Result<Self> {
        let dir = root.join(session_id.to_string());
        fs::create_dir_all(&dir)?;
        Ok(Self {
            dir,
            inner: Mutex::new(()),
        })
    }

    fn chunk_path(&self, chunk_seq: u64) -> PathBuf {
        self.dir.join(format!("{chunk_seq:010}.chunk"))
    }

    /// Persiste un fragment (fsync) avant envoi.
    pub fn store(&self, chunk: &ChunkOut) -> std::io::Result<()> {
        let _g = self.inner.lock();
        let path = self.chunk_path(chunk.chunk_seq);
        let mut f = fs::File::create(&path)?;
        // Format simple : chunk_end JSON sur la 1re ligne, puis trames séparées par \n
        writeln!(f, "{}", chunk.chunk_end)?;
        for frame in &chunk.frames {
            // base64 pour éviter les octets binaires dans le fichier texte
            writeln!(f, "{}", base64_encode(frame))?;
        }
        f.sync_all()?;
        Ok(())
    }

    /// Efface un fragment après ACK.
    pub fn ack(&self, chunk_seq: u64) -> std::io::Result<()> {
        let _g = self.inner.lock();
        let path = self.chunk_path(chunk_seq);
        if path.exists() {
            fs::remove_file(path)?;
        }
        Ok(())
    }

    /// Liste les fragments non acquittés (à réémettre après reconnexion).
    pub fn pending(&self) -> Vec<u64> {
        let _g = self.inner.lock();
        let mut seqs = Vec::new();
        if let Ok(entries) = fs::read_dir(&self.dir) {
            for e in entries.flatten() {
                if let Some(name) = e.file_name().to_str() {
                    if let Some(stem) = name.strip_suffix(".chunk") {
                        if let Ok(seq) = stem.parse::<u64>() {
                            seqs.push(seq);
                        }
                    }
                }
            }
        }
        seqs.sort_unstable();
        seqs
    }

    /// Relit un fragment du spool (pour réémission).
    pub fn load(&self, chunk_seq: u64) -> std::io::Result<Option<ChunkOut>> {
        let _g = self.inner.lock();
        let path = self.chunk_path(chunk_seq);
        if !path.exists() {
            return Ok(None);
        }
        let content = fs::read_to_string(&path)?;
        let mut lines = content.lines();
        let chunk_end = match lines.next() {
            Some(l) => l.to_string(),
            None => return Ok(None),
        };
        let mut frames = Vec::new();
        for line in lines {
            if let Some(bytes) = base64_decode(line) {
                frames.push(bytes);
            }
        }
        let sha256 = extract_sha(&chunk_end);
        Ok(Some(ChunkOut {
            chunk_seq,
            frames,
            chunk_end,
            sha256,
        }))
    }

    /// Nettoie tout le spool (fin de session).
    pub fn clear(&self) {
        let _g = self.inner.lock();
        let _ = fs::remove_dir_all(&self.dir);
    }
}

fn extract_sha(chunk_end: &str) -> String {
    // Extrait "sha256":"..." du JSON
    if let Some(pos) = chunk_end.find("\"sha256\":\"") {
        let rest = &chunk_end[pos + 10..];
        if let Some(end) = rest.find('"') {
            return rest[..end].to_string();
        }
    }
    String::new()
}

fn base64_encode(data: &[u8]) -> String {
    use base64::Engine;
    base64::engine::general_purpose::STANDARD.encode(data)
}

fn base64_decode(s: &str) -> Option<Vec<u8>> {
    use base64::Engine;
    base64::engine::general_purpose::STANDARD.decode(s).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chunker_produces_full_chunk() {
        let sid = Uuid::new_v4();
        let mut c = Chunker::new(sid);
        // 10 s = 160000 échantillons = 40 trames de 4000
        let samples = vec![0.0f32; FRAME_SAMPLES * FRAMES_PER_CHUNK];
        let chunks = c.push(&samples);
        assert_eq!(chunks.len(), 1);
        assert_eq!(chunks[0].chunk_seq, 0);
        assert_eq!(chunks[0].frames.len(), FRAMES_PER_CHUNK);
        assert_eq!(chunks[0].sha256.len(), 64);
    }

    #[test]
    fn chunker_finish_partial() {
        let sid = Uuid::new_v4();
        let mut c = Chunker::new(sid);
        c.push(&vec![0.0f32; FRAME_SAMPLES]); // 1 trame
        let last = c.finish();
        assert!(last.is_some());
        assert_eq!(last.unwrap().frames.len(), 1);
    }

    #[test]
    fn spool_store_ack_pending() {
        let tmp = std::env::temp_dir().join(format!("revizio-spool-{}", Uuid::new_v4()));
        let sid = Uuid::new_v4();
        let spool = Spool::new(&tmp, sid).unwrap();
        let mut c = Chunker::new(sid);
        let chunks = c.push(&vec![0.0f32; FRAME_SAMPLES * FRAMES_PER_CHUNK]);
        spool.store(&chunks[0]).unwrap();
        assert_eq!(spool.pending(), vec![0]);
        let loaded = spool.load(0).unwrap().unwrap();
        assert_eq!(loaded.frames.len(), FRAMES_PER_CHUNK);
        spool.ack(0).unwrap();
        assert!(spool.pending().is_empty());
        spool.clear();
    }
}
