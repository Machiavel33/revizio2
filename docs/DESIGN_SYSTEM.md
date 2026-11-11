# Coursify — Design System "DarkPunk Pro"

> Direction artistique : **DarkPunk futuriste, mais professionnel.**
> Sombre, profond, néon maîtrisé, géométrique. Pas de cyberpunk criard de gamer.
> Du raffinement sombre qui inspire confiance à un étudiant et à un admin.

---

## 1. Philosophie visuelle

Trois mots : **Sombre. Précis. Vivant.**

- **Sombre** : fonds profonds (pas du noir pur — du bleu-nuit charbonné), contraste élevé mais doux pour les yeux (sessions de révision longues).
- **Précis** : grille stricte, alignements chirurgicaux, typographie géométrique. Le "pro" vient de la rigueur, pas de la décoration.
- **Vivant** : micro-animations, halos néon subtils, états réactifs. Le "futuriste" vient du mouvement et de la lumière, pas du bruit visuel.

**Règle d'or :** le néon est un **accent**, jamais un fond. 90% de l'interface est sombre et sobre, 10% pulse. C'est ce ratio qui sépare le pro du kitsch.

---

## 2. Palette de couleurs

### Fonds (surfaces)
| Token | Hex | Usage |
|---|---|---|
| `--bg-base` | `#0A0B0F` | Fond principal (bleu-nuit quasi noir) |
| `--bg-surface` | `#12141C` | Cartes, panneaux |
| `--bg-elevated` | `#1A1D28` | Modales, dropdowns, éléments surélevés |
| `--bg-inset` | `#07080B` | Zones creuses (inputs, code) |

### Accents néon (le "punk")
| Token | Hex | Usage |
|---|---|---|
| `--accent-primary` | `#00E5FF` | Cyan électrique — action principale, focus |
| `--accent-secondary` | `#B14EFF` | Violet néon — accents secondaires, gradients |
| `--accent-success` | `#00FFA3` | Vert menthe — succès, "ready", enregistrement OK |
| `--accent-warning` | `#FFB800` | Ambre — avertissements |
| `--accent-danger` | `#FF3B5C` | Rouge néon — erreurs, suppression, REC |

### Texte
| Token | Hex | Usage |
|---|---|---|
| `--text-primary` | `#F0F2F8` | Texte principal |
| `--text-secondary` | `#A0A6B8` | Texte secondaire, labels |
| `--text-muted` | `#5C6274` | Placeholders, désactivé |
| `--text-on-accent` | `#0A0B0F` | Texte sur fond néon (contraste) |

### Bordures & séparateurs
| Token | Hex | Usage |
|---|---|---|
| `--border-subtle` | `#1F2330` | Bordures discrètes |
| `--border-strong` | `#2E3444` | Bordures marquées |
| `--border-glow` | `rgba(0,229,255,0.35)` | Bordure lumineuse au focus/hover |

### Gradients signature
```css
/* Gradient principal (boutons, titres) */
--grad-primary: linear-gradient(135deg, #00E5FF 0%, #B14EFF 100%);

/* Halo d'ambiance (arrière-plans de section) */
--grad-ambient: radial-gradient(circle at 30% 0%, rgba(0,229,255,0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 100%, rgba(177,78,255,0.08) 0%, transparent 50%);

/* Enregistrement actif (pulse) */
--grad-rec: linear-gradient(135deg, #FF3B5C 0%, #FFB800 100%);
```

---

## 3. Typographie

| Rôle | Police | Fallback | Poids |
|---|---|---|---|
| Display / Titres | **Space Grotesk** | system-ui | 500, 700 |
| Corps / UI | **Inter** | system-ui | 400, 500, 600 |
| Mono / Code / Timestamps | **JetBrains Mono** | monospace | 400, 500 |

**Pourquoi :** Space Grotesk = géométrique, futuriste, lisible en gros titres. Inter = neutre, pro, parfait en UI dense. JetBrains Mono = timestamps de transcription, données techniques.

### Échelle typographique
```css
--text-xs:   0.75rem;  /* 12px — labels, badges */
--text-sm:   0.875rem; /* 14px — UI secondaire */
--text-base: 1rem;     /* 16px — corps */
--text-lg:   1.125rem; /* 18px — sous-titres */
--text-xl:   1.5rem;   /* 24px — titres de section */
--text-2xl:  2rem;     /* 32px — titres de page */
--text-3xl:  2.75rem;  /* 44px — hero */
```

**Interlignage :** 1.5 corps, 1.2 titres. **Letter-spacing :** -0.02em sur les gros titres (resserre = moderne), +0.05em sur les labels en majuscules (aération).

---

## 4. Espacement & grille

Base 4px. Échelle : `4, 8, 12, 16, 24, 32, 48, 64, 96`.

- **Container max-width :** 1280px (web), 100% (desktop app).
- **Grille :** 12 colonnes, gutter 24px.
- **Rayons de bordure :** `--radius-sm: 6px`, `--radius-md: 12px`, `--radius-lg: 20px`, `--radius-full: 9999px`.

---

## 5. Élévation & profondeur

Pas d'ombres noires lourdes. On utilise **lumière + profondeur** :

```css
/* Carte standard */
--shadow-card: 0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03);

/* Carte surélevée (hover) */
--shadow-elevated: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,229,255,0.15);

/* Glow néon (focus, bouton actif) */
--shadow-glow-cyan: 0 0 20px rgba(0,229,255,0.4), 0 0 40px rgba(0,229,255,0.15);
--shadow-glow-violet: 0 0 20px rgba(177,78,255,0.4), 0 0 40px rgba(177,78,255,0.15);
```

**Glassmorphism discret** (modales, headers flottants) :
```css
--glass-bg: rgba(18,20,28,0.7);
--glass-blur: blur(16px) saturate(140%);
--glass-border: 1px solid rgba(255,255,255,0.06);
```

---

## 6. Composants clés

### Boutons
- **Primary** : gradient cyan→violet, texte sombre, glow au hover, scale 1.02.
- **Secondary** : surface + bordure subtile, texte clair, bordure glow au hover.
- **Ghost** : transparent, texte secondaire, fond subtil au hover.
- **Danger** : rouge néon, pour suppression.
- **Recording** : rouge→ambre avec **pulse animé** (le seul élément qui respire en permanence).

### Inputs
- Fond `--bg-inset`, bordure subtile, focus → bordure `--border-glow` + `--shadow-glow-cyan`.
- Labels en majuscules `--text-xs`, letter-spacing large.

### Cartes de cours
- Surface `--bg-surface`, bordure subtile, hover → élévation + bordure glow.
- Barre de statut colorée à gauche (recording=rouge pulse, ready=vert, processing=cyan animé).

### Badges de statut
- Pill, fond translucide de la couleur d'accent (ex. `rgba(0,255,163,0.12)`), texte de la couleur pleine, point lumineux.

### Waveform (enregistrement)
- Visualiseur audio temps réel : barres verticales cyan→violet, réactives au niveau micro. **Signature visuelle de l'app.**

---

## 7. Micro-animations (le "futuriste vivant")

| Élément | Animation | Durée |
|---|---|---|
| Bouton hover | scale 1.02 + glow | 150ms ease-out |
| Carte hover | translateY(-2px) + shadow | 200ms ease-out |
| Modal open | fade + scale 0.96→1 | 250ms cubic-bezier(0.16,1,0.3,1) |
| Recording pulse | opacity/scale halo | 1.5s infinite |
| Transcription live | fade-in par mot | 80ms |
| Page transition | fade + slide 8px | 300ms |
| Skeleton loaders | shimmer gradient | 1.2s infinite |

**Règle :** jamais plus de 300ms, jamais de bounce excessif. Le mouvement est fluide et confiant, pas joueur.

---

## 8. Iconographie

- **Lucide Icons** (stroke 1.5px, cohérent, léger).
- Couleur `--text-secondary` par défaut, `--accent-primary` quand actif.
- Taille : 16px (inline), 20px (boutons), 24px (nav).

---

## 9. Accessibilité (non négociable)

- **Contraste** : texte principal ≥ 7:1 sur fond (AAA). Texte secondaire ≥ 4.5:1 (AA).
- **Focus visible** : toujours un anneau `--shadow-glow-cyan` — jamais `outline: none` sans remplacement.
- **Pas de néon sur texte long** : le néon est réservé aux accents courts (boutons, badges, titres hero).
- **Reduced motion** : respecter `prefers-reduced-motion` → désactiver pulse et transitions.
- **Daltonisme** : ne jamais coder l'info par la couleur seule (toujours + icône/texte).

---

## 10. Implémentation technique

### Tailwind config (extrait)
```js
// tailwind.config.js
export default {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: { base: '#0A0B0F', surface: '#12141C', elevated: '#1A1D28', inset: '#07080B' },
        accent: { primary: '#00E5FF', secondary: '#B14EFF', success: '#00FFA3', warning: '#FFB800', danger: '#FF3B5C' },
        text: { primary: '#F0F2F8', secondary: '#A0A6B8', muted: '#5C6274' },
        border: { subtle: '#1F2330', strong: '#2E3444' },
      },
      fontFamily: {
        display: ['Space Grotesk', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        card: '0 4px 24px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03)',
        'glow-cyan': '0 0 20px rgba(0,229,255,0.4), 0 0 40px rgba(0,229,255,0.15)',
        'glow-violet': '0 0 20px rgba(177,78,255,0.4), 0 0 40px rgba(177,78,255,0.15)',
      },
      borderRadius: { sm: '6px', md: '12px', lg: '20px' },
    },
  },
}
```

### Variables CSS globales
```css
/* globals.css */
:root {
  --bg-base: #0A0B0F;
  --bg-surface: #12141C;
  --bg-elevated: #1A1D28;
  --bg-inset: #07080B;
  --accent-primary: #00E5FF;
  --accent-secondary: #B14EFF;
  --accent-success: #00FFA3;
  --accent-warning: #FFB800;
  --accent-danger: #FF3B5C;
  --text-primary: #F0F2F8;
  --text-secondary: #A0A6B8;
  --text-muted: #5C6274;
  --border-subtle: #1F2330;
  --border-strong: #2E3444;
  --grad-primary: linear-gradient(135deg, #00E5FF 0%, #B14EFF 100%);
  --grad-ambient: radial-gradient(circle at 30% 0%, rgba(0,229,255,0.08) 0%, transparent 50%),
                  radial-gradient(circle at 80% 100%, rgba(177,78,255,0.08) 0%, transparent 50%);
  --glass-bg: rgba(18,20,28,0.7);
  --glass-blur: blur(16px) saturate(140%);
}

body {
  background: var(--bg-base);
  background-image: var(--grad-ambient);
  color: var(--text-primary);
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}
```

### Stack UI
- **Tailwind CSS** + **shadcn/ui** (composants headless, on les re-thème avec notre palette).
- **Framer Motion** pour les animations (desktop + web).
- **Lucide React** pour les icônes.
- **Recharts** pour les stats admin (thémé sombre).

---

## 11. Cohérence desktop ↔ web

Le **même design system** est partagé via `packages/shared/design-tokens` (export des tokens CSS + config Tailwind). Le desktop Tauri et le web React consomment les mêmes tokens → identité visuelle unifiée.

---

## 12. Écrans clés (aperçu de la direction)

- **Desktop — Enregistrement** : fond sombre, waveform cyan/violet plein écran, bouton REC rouge pulsant, transcription live en mono à droite qui défile, timer géant Space Grotesk.
- **Desktop — Fiche générée** : carte glassmorphism, sections aérées, flashcards en accordéon, bouton export PDF gradient.
- **Web étudiant — Dashboard** : grille de cartes de cours, barres de statut colorées, header glass flottant, recherche avec focus glow.
- **Web admin — Supervision** : table dense, badges de statut, graphiques Recharts sombres, sidebar avec indicateurs néon.
