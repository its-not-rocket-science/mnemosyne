/**
 * subcategory-labels.js — pure data module, no DOM dependencies.
 * Safe to import from Web Components and mode coordinators alike.
 */

const LABELS = {
  // Chinese
  chengyu:           '成语',      xiehouyu:          '歇后语',
  suyv:              '俗语',      yanyu:             '谚语',
  // Arabic
  quranic:           'قرآن',      hadith:            'حديث',
  muallaqat:         'معلقة',     abbasid:           'عباسي',
  modern_media:      'Media',
  // Persian
  shahnameh:         'شاهنامه',   hafez:             'حافظ',
  rumi:              'رومی',      saadi:             'سعدی',
  khayyam:           'خیام',      persian_proverb:   'ضرب المثل',
  // Japanese
  yojijukugo:        '四字熟語',   kanyoku:           '慣用句',
  kotowaza:          'ことわざ',    zen_koan:          '公案',
  // Korean
  sajaseong_eo:      '사자성어',   pansori:           '판소리',
  sijo:              '시조',       korean_proverb:    '속담',
  // Hindi
  doha_kabir:        'कबीर',      doha_rahim:        'रहीम',
  ramcharitmanas:    'रामचरितमानस', bhagavad_gita:   'गीता',
  panchatantra:      'पञ्चतन्त्र', filmi:            'फ़िल्मी',
  hindi_muhavare:    'मुहावरा',    hindi_lokokti:    'लोकोक्ति',
  // Universal
  biblical:          'Biblical',   shakespearean:    'Shakespeare',
  latin_tag:         'Latin',      greek_tag:        'Greek',
  literary_allusion: 'Literary',   proverb:          'Proverb',
}

export function subcategoryLabel(sub) {
  return LABELS[sub] ?? sub.replace(/_/g, ' ')
}
