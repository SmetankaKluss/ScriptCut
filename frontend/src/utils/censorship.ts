import type { Word } from '../types/project';

export type CensorMatch = {
  id: string;
  startWordIndex: number;
  endWordIndex: number;
  startTime: number;
  endTime: number;
  text: string;
  source: 'built-in' | 'custom';
  confidence: number;
  matchKind: 'exact' | 'split' | 'obfuscated' | 'custom';
  reason: string;
};

type ProfanityRule = {
  id: string;
  label: string;
  patterns: RegExp[];
};

// These are morphology-aware families rather than a flat list. They cover the
// common inflections and streamer-style distortions that ASR produces, while
// keeping every pattern anchored so innocent substrings such as "страхуй" are
// not flagged merely because they end in the same letters.
const RUSSIAN_PROFANITY_RULES: ProfanityRule[] = [
  {
    id: 'blyad',
    label: 'семейство «блядь»',
    patterns: [
      /^бл(?:я|е|иа)(?:д|т|ть)?[а-я]*$/u,
      /^бл(?:е|и)ат[а-я]*$/u,
    ],
  },
  {
    id: 'khuy',
    label: 'семейство «хуй»',
    patterns: [
      /^(?:(?:на|по|о|а|за|до|вы|про|при|не|об)?ху(?:й|я|е|и|ю|ев|ёв))[а-я]*$/u,
      /^ху(?:есос|еплет|еплёт|йн)[а-я]*$/u,
    ],
  },
  {
    id: 'pizda',
    label: 'семейство «пизда»',
    patterns: [
      /^(?:(?:рас|за|на|по|про|вы|от|до|при|под)?п(?:и|е|ы)[зс]д)[а-я]*$/u,
    ],
  },
  {
    id: 'ebat',
    label: 'семейство «ебать»',
    patterns: [
      /^(?:(?:за|на|по|про|вы|у|до|от|под|пере|при|с|вз|об)?[ъь]?(?:е|э|и|йо|ио)б)[а-я]*$/u,
      /^(?:епт|епта|ептить|йопт|йопта)[а-я]*$/u,
      /^(?:долбоеб|мозгоеб|скотоеб)[а-я]*$/u,
    ],
  },
  {
    id: 'suka',
    label: 'семейство «сука»',
    patterns: [
      /^сук(?:а|и|у|ой|ою|е|ам|ами)?$/u,
      /^суч(?:ка|ки|ку|кой|ара|ий|ье|онок|оны)[а-я]*$/u,
    ],
  },
  {
    id: 'insults',
    label: 'грубая обсценная лексика',
    patterns: [
      /^(?:мудак|мудила|мудозвон)[а-я]*$/u,
      /^(?:гандон|гондон)[а-я]*$/u,
      /^(?:пидор|пидар|пидарас|пидорас|педераст|педик)[а-я]*$/u,
      /^(?:шлюх|залуп|мандов|мандав)[а-я]*$/u,
    ],
  },
];

const LOOKALIKE_MAP: Record<string, string> = {
  a: 'а',
  b: 'б',
  c: 'с',
  e: 'е',
  k: 'к',
  m: 'м',
  o: 'о',
  p: 'р',
  t: 'т',
  x: 'х',
  y: 'у',
  '0': 'о',
  '3': 'е',
  '4': 'ч',
  '6': 'б',
  '@': 'а',
  '$': 'с',
};

export function findCensorMatches(
  words: Word[],
  customInput: string,
  includeBuiltIn = true,
): CensorMatch[] {
  const matches: CensorMatch[] = [];
  const seen = new Set<string>();
  const normalizedWords = words.map((word) => normalizeToken(word.word));

  const addMatch = (
    startWordIndex: number,
    endWordIndex: number,
    source: CensorMatch['source'],
    details?: Partial<Pick<CensorMatch, 'confidence' | 'matchKind' | 'reason'>>,
  ) => {
    const key = `${startWordIndex}:${endWordIndex}`;
    if (seen.has(key)) return;
    const startWord = words[startWordIndex];
    const endWord = words[endWordIndex];
    if (!startWord || !endWord) return;
    seen.add(key);
    matches.push({
      id: `censor_${source}_${startWordIndex}_${endWordIndex}`,
      startWordIndex,
      endWordIndex,
      startTime: Math.max(0, startWord.start - 0.08),
      endTime: endWord.end + 0.12,
      text: words.slice(startWordIndex, endWordIndex + 1).map((word) => word.word).join(' '),
      source,
      confidence: details?.confidence ?? (source === 'custom' ? 1 : 0.98),
      matchKind: details?.matchKind ?? (source === 'custom' ? 'custom' : 'exact'),
      reason: details?.reason ?? (source === 'custom' ? 'Совпадение с вашим списком' : 'Русский словарь'),
    });
  };

  if (includeBuiltIn) {
    normalizedWords.forEach((token, index) => {
      const rule = findProfanityRule(token);
      if (!rule) return;
      const obfuscated = isObfuscatedSurface(words[index]?.word || '');
      addMatch(index, index, 'built-in', {
        confidence: obfuscated ? 0.94 : 0.99,
        matchKind: obfuscated ? 'obfuscated' : 'exact',
        reason: obfuscated
          ? `${rule.label}: распознана замаскированная запись`
          : rule.label,
      });
    });

    // Speech-to-text often separates a short profanity into syllables or even
    // letters ("е бал", "б л я т ь", "на хуй"). Join only short spans and
    // require the complete joined form to match an anchored family.
    for (let start = 0; start < normalizedWords.length; start++) {
      if (findProfanityRule(normalizedWords[start])) continue;
      let joined = '';
      for (let end = start; end < Math.min(normalizedWords.length, start + 6); end++) {
        const part = normalizedWords[end];
        if (!part || part.length > 5) break;
        joined += part;
        if (end === start) continue;
        const rule = findProfanityRule(joined);
        if (!rule) continue;
        const overlapsKnownMatch = matches.some(
          (match) =>
            match.source === 'built-in' &&
            match.startWordIndex <= end &&
            match.endWordIndex >= start,
        );
        if (overlapsKnownMatch) break;
        addMatch(start, end, 'built-in', {
          confidence: 0.93,
          matchKind: 'split',
          reason: `${rule.label}: слово было разбито распознаванием`,
        });
        break;
      }
    }
  }

  for (const phrase of parseCustomPhrases(customInput)) {
    if (phrase.length === 0 || phrase.length > normalizedWords.length) continue;
    for (let start = 0; start <= normalizedWords.length - phrase.length; start++) {
      if (phrase.every((token, offset) => normalizedWords[start + offset] === token)) {
        addMatch(start, start + phrase.length - 1, 'custom');
      }
    }
  }

  return matches.sort(
    (left, right) =>
      left.startWordIndex - right.startWordIndex ||
      left.endWordIndex - right.endWordIndex,
  );
}

export function parseCustomPhrases(input: string): string[][] {
  return input
    .split(/[,\n;]+/u)
    .map((phrase) =>
      phrase
        .trim()
        .split(/\s+/u)
        .map(normalizeToken)
        .filter(Boolean),
    )
    .filter((phrase) => phrase.length > 0);
}

export function normalizeToken(value: string): string {
  const normalized = value.toLocaleLowerCase('ru-RU').normalize('NFKC');
  const shouldMapLookalikes =
    /[а-яё]/u.test(normalized) ||
    (/[a-z]/u.test(normalized) && /[0-9@$*#_]/u.test(normalized));
  const mapped = shouldMapLookalikes
    ? [...normalized].map((character) => LOOKALIKE_MAP[character] || character).join('')
    : normalized;

  return mapped
    .replace(/ё/gu, 'е')
    .replace(/[^\p{L}]/gu, '')
    .replace(/(.)\1{1,}/gu, '$1');
}

function findProfanityRule(value: string): ProfanityRule | undefined {
  if (!value || value.length < 3) return undefined;
  return RUSSIAN_PROFANITY_RULES.find((rule) =>
    rule.patterns.some((pattern) => pattern.test(value)),
  );
}

function isObfuscatedSurface(value: string): boolean {
  return /[a-z0-9@$*#_]/iu.test(value) || /[\p{L}][.\-_/\\*]+[\p{L}]/u.test(value);
}
