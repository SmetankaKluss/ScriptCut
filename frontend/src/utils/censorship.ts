import type { Word } from '../types/project';

export type CensorMatch = {
  id: string;
  startWordIndex: number;
  endWordIndex: number;
  startTime: number;
  endTime: number;
  text: string;
  source: 'built-in' | 'custom';
};

const BUILT_IN_RUSSIAN_PATTERNS = [
  /^бл(?:я|е)(?:д|т)?[а-я]*$/u,
  /^ху(?:й|я|е|и|ю)[а-я]*$/u,
  /^(?:пизд|пезд)[а-я]*$/u,
  /^(?:еб|ебан|ебуч|ебл)[а-я]*$/u,
  /^долбоеб[а-я]*$/u,
  /^мудак[а-я]*$/u,
  /^сук(?:а|и|у|ой|е)?$/u,
  /^гандон[а-я]*$/u,
];

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
      startTime: startWord.start,
      endTime: endWord.end,
      text: words.slice(startWordIndex, endWordIndex + 1).map((word) => word.word).join(' '),
      source,
    });
  };

  if (includeBuiltIn) {
    normalizedWords.forEach((word, index) => {
      if (word && BUILT_IN_RUSSIAN_PATTERNS.some((pattern) => pattern.test(word))) {
        addMatch(index, index, 'built-in');
      }
    });
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
  return value
    .toLocaleLowerCase('ru-RU')
    .replace(/ё/gu, 'е')
    .replace(/[0-9_]/gu, '')
    .replace(/[^\p{L}-]/gu, '')
    .replace(/^-+|-+$/gu, '');
}
