/**
 * subcategory-labels.js — pure data module, no DOM dependencies.
 * Safe to import from Web Components and mode coordinators alike.
 * Keep in sync with _SUBCATEGORY_VALUES in scripts/extend_cultural_catalogue.py.
 */

const LABELS = {
  // ── Chinese ───────────────────────────────────────────────────────────
  chengyu:                '成语',       xiehouyu:              '歇后语',
  suyv:                   '俗语',       yanyu:                 '谚语',

  // ── Arabic ────────────────────────────────────────────────────────────
  quranic:                'قرآن',       hadith:                'حديث',
  muallaqat:              'معلقة',      abbasid:               'عباسي',
  modern_media:           'Media',

  // ── Persian ───────────────────────────────────────────────────────────
  shahnameh:              'شاهنامه',    hafez:                 'حافظ',
  rumi:                   'رومی',       saadi:                 'سعدی',
  khayyam:                'خیام',       attar:                 'عطار',
  nizami:                 'نظامی',      sufi_poetry:           'تصوف',
  persian_proverb:        'ضرب المثل',

  // ── Japanese ──────────────────────────────────────────────────────────
  yojijukugo:             '四字熟語',    kanyoku:               '慣用句',
  kotowaza:               'ことわざ',     zen_koan:              '公案',
  classical_literature:   'Classical',  buddhist_text:         '仏典',
  mythology:              'Mythology',

  // ── Korean ────────────────────────────────────────────────────────────
  sajaseong_eo:           '사자성어',    pansori:               '판소리',
  sijo:                   '시조',        korean_proverb:        '속담',
  confucian_text:         '유교',        folk_tale:             'Folk tale',

  // ── Hindi ─────────────────────────────────────────────────────────────
  doha_kabir:             'कबीर',       doha_rahim:            'रहीम',
  ramcharitmanas:         'रामचरितमानस', bhagavad_gita:        'गीता',
  mahabharata:            'महाभारत',     panchatantra:          'पञ्चतन्त्र',
  vedic_scripture:        'वेद',         filmi:                 'फ़िल्मी',
  hindi_muhavare:         'मुहावरा',     hindi_lokokti:         'लोकोक्ति',

  // ── Hindi (extended) ──────────────────────────────────────────────────
  classical_sanskrit:     'Sanskrit',    hindu_philosophy:      'Hindu phil.',

  // ── Hebrew ────────────────────────────────────────────────────────────
  talmudic:               'Talmud',      kabbalistic:          'Kabbalah',
  liturgical:             'Liturgy',     modern_hebrew:        'Modern Heb.',

  // ── Russian ───────────────────────────────────────────────────────────
  pushkin:                'Пушкин',      poslovitsa:           'пословица',

  // ── German ────────────────────────────────────────────────────────────
  goethe_schiller:        'Goethe',      fairy_tale:           'Märchen',
  nibelungen:             'Nibelungen',  opera_libretto:       'Opera',
  sprichwort:             'Sprichwort',

  // ── Italian ───────────────────────────────────────────────────────────
  dantesque:              'Dante',       renaissance_literature: 'Renaissance',
  proverbio:              'Proverbio',

  // ── Spanish ───────────────────────────────────────────────────────────
  golden_age:             'Siglo de Oro', quijote:             'Quijote',
  latin_american_literature: 'Lat. Am.', latin_american_history: 'Lat. Am. hist.',
  refran:                 'Refrán',

  // ── Portuguese ────────────────────────────────────────────────────────
  camoniano:              'Camões',      brazilian_literature: 'Brasil',

  // ── French ────────────────────────────────────────────────────────────
  classical_tragedy:      'Tragédie',    enlightenment:        'Lumières',
  proverbe:               'Proverbe',

  // ── Turkish ───────────────────────────────────────────────────────────
  ottoman_literature:     'Osmanlı',     divan_poetry:         'Divan',
  folk_poetry:            'Folk şiir',   atassözü:             'Atasözü',

  // ── Finnish ───────────────────────────────────────────────────────────
  kalevala:               'Kalevala',    sananlasku:           'Sananlasku',

  // ── Universal cross-language ──────────────────────────────────────────
  biblical:               'Biblical',    shakespearean:        'Shakespeare',
  arthurian:              'Arthurian',   greek_mythology:      'Greek myth',
  roman_mythology:        'Roman myth',  norse_mythology:      'Norse myth',
  latin_tag:              'Latin',       greek_tag:            'Greek',
  literary_allusion:      'Literary',    modern_literature:    'Literature',
  classical:              'Classical',   proverb:              'Proverb',
  science_fiction:        'Sci-fi',      visual_art:           'Visual art',
  visual_art_movement:    'Art movement', historical:          'Historical',
  historical_figure:      'Figure',      political_history:    'Political',
  film_tv:                'Film & TV',   music:                'Music',
  sport:                  'Sport',

  // ── The essential catchall ────────────────────────────────────────────
  idiom:                  'Idiom',
}

export function subcategoryLabel(sub) {
  return LABELS[sub] ?? sub.replace(/_/g, ' ')
}
