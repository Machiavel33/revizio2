//! Protocole audio résilient Revizio v1 (miroir du backend `app/transport/protocol.py`).
//!
//! Trame binaire = en-tête fixe little-endian de 44 octets + PCM s16le mono 16 kHz.
//!
//! ```text
//! offset  taille  champ
//! 0       4       magic          b"RVZF"
//! 4       1       version        1
//! 5       1       flags          0
//! 6       2       reserved       0
//! 8       16      session_id     UUID (octets big-endian)
//! 24      8       frame_seq      uint64, 0-based
//! 32      8       sample_offset  uint64
//! 40      4       sample_count   uint32, 1..4000
//! ```
//!
//! Invariants : trame pleine = 4000 échantillons (250 ms) ; `sample_offset == frame_seq * 4000` ;
//! `chunk_seq = frame_seq / 40` ; un fragment = 40 trames = 10 s ; SHA-256 sur le PCM concaténé.

use sha2::{Digest, Sha256};
use uuid::Uuid;

pub const MAGIC: &[u8; 4] = b"RVZF";
pub const PROTOCOL_VERSION: u8 = 1;
#[allow(dead_code)]
pub const SAMPLE_RATE: u32 = 16_000;
pub const BYTES_PER_SAMPLE: usize = 2;
pub const FRAME_SAMPLES: usize = 4_000;
#[allow(dead_code)]
pub const FRAME_BYTES: usize = FRAME_SAMPLES * BYTES_PER_SAMPLE;
pub const FRAMES_PER_CHUNK: usize = 40;
pub const CHUNK_SAMPLES: usize = FRAME_SAMPLES * FRAMES_PER_CHUNK;
pub const HEADER_SIZE: usize = 44;

/// Encode une trame binaire (en-tête 44o + PCM s16le).
pub fn encode_frame(session_id: Uuid, frame_seq: u64, pcm: &[u8]) -> Vec<u8> {
    let sample_count = (pcm.len() / BYTES_PER_SAMPLE) as u32;
    let sample_offset = frame_seq * FRAME_SAMPLES as u64;
    let mut out = Vec::with_capacity(HEADER_SIZE + pcm.len());
    out.extend_from_slice(MAGIC);
    out.push(PROTOCOL_VERSION);
    out.push(0); // flags
    out.extend_from_slice(&0u16.to_le_bytes()); // reserved
    out.extend_from_slice(session_id.as_bytes()); // 16 octets big-endian
    out.extend_from_slice(&frame_seq.to_le_bytes());
    out.extend_from_slice(&sample_offset.to_le_bytes());
    out.extend_from_slice(&sample_count.to_le_bytes());
    out.extend_from_slice(pcm);
    out
}

/// Convertit des échantillons f32 (-1..1) en PCM s16le.
pub fn f32_to_pcm16(samples: &[f32]) -> Vec<u8> {
    let mut out = Vec::with_capacity(samples.len() * 2);
    for &s in samples {
        let v = (s.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        out.extend_from_slice(&v.to_le_bytes());
    }
    out
}

/// SHA-256 hexadécimal d'un fragment (PCM concaténé).
pub fn pcm_sha256(pcm: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(pcm);
    let digest = hasher.finalize();
    let mut s = String::with_capacity(64);
    for b in digest {
        s.push_str(&format!("{b:02x}"));
    }
    s
}

/// Message `chunk_end` (JSON) à envoyer après les 40 trames d'un fragment.
pub fn chunk_end_json(chunk_seq: u64, frame_count: usize, sample_count: usize, sha256: &str) -> String {
    let sample_offset = chunk_seq * CHUNK_SAMPLES as u64;
    format!(
        "{{\"type\":\"chunk_end\",\"chunk_seq\":{chunk_seq},\"frame_count\":{frame_count},\
         \"sample_offset\":{sample_offset},\"sample_count\":{sample_count},\"sha256\":\"{sha256}\"}}"
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frame_header_is_44_bytes() {
        let sid = Uuid::new_v4();
        let pcm = vec![0u8; FRAME_BYTES];
        let frame = encode_frame(sid, 0, &pcm);
        assert_eq!(frame.len(), HEADER_SIZE + FRAME_BYTES);
        assert_eq!(&frame[0..4], MAGIC);
        assert_eq!(frame[4], PROTOCOL_VERSION);
        // sample_count à l'offset 40
        let sc = u32::from_le_bytes(frame[40..44].try_into().unwrap());
        assert_eq!(sc as usize, FRAME_SAMPLES);
    }

    #[test]
    fn sample_offset_matches_seq() {
        let sid = Uuid::new_v4();
        let frame = encode_frame(sid, 3, &vec![0u8; FRAME_BYTES]);
        let off = u64::from_le_bytes(frame[32..40].try_into().unwrap());
        assert_eq!(off, 3 * FRAME_SAMPLES as u64);
    }

    #[test]
    fn sha256_is_stable() {
        let pcm = vec![1u8, 2, 3, 4];
        let a = pcm_sha256(&pcm);
        let b = pcm_sha256(&pcm);
        assert_eq!(a, b);
        assert_eq!(a.len(), 64);
    }

    #[test]
    fn chunk_end_json_well_formed() {
        let j = chunk_end_json(0, 40, CHUNK_SAMPLES, &"a".repeat(64));
        assert!(j.contains("\"type\":\"chunk_end\""));
        assert!(j.contains("\"chunk_seq\":0"));
        assert!(j.contains("\"sample_offset\":0"));
    }
}
