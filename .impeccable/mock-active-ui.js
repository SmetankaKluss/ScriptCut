async page => {
  await page.addInitScript(() => {
    window.localStorage.setItem('scriptcut.onboarding.dismissed.v1', 'true');
    window.electronAPI = {
      getBackendUrl: async () => 'http://127.0.0.1:8642',
      getStartupStatus: async () => ({ backendError: null }),
      openFile: async () => '/demo/stream.mp4',
      openProject: async () => null,
      readProjectFile: async () => {
        throw new Error('No saved project');
      },
      writeProjectFile: async () => {},
      saveFile: async () => null,
      quit: async () => {},
    };
  });

  const transcript = [
    'Ребят сегодня разберём почему эта механика вообще не оптимизирована',
    'я сначала думал что всё работает нормально но потом начался полный пиздец',
    'вот здесь мы спокойно поднимаемся наверх и поворачиваем направо',
    'блять этот моб опять появился прямо перед камерой',
    'ладно оставим только разговор про оптимизацию и вырежем лишний гринд',
    'если коротко проблема не в игроке а в том как считается каждый тик',
    'поэтому на слабом компьютере всё начинает тормозить и звук заикается',
    'в финальной нарезке добавим субтитры и запикаем спорные слова',
  ];
  let cursor = 0;
  const segments = transcript.map((text, id) => {
    const segmentWords = text.split(' ').map((word, index) => {
      const item = {
        word,
        start: cursor,
        end: cursor + 0.42,
        confidence: word === 'пиздец' ? 0.58 : 0.92 + ((index % 6) * 0.01),
      };
      cursor += 0.48;
      return item;
    });
    return {
      id,
      start: segmentWords[0].start,
      end: segmentWords[segmentWords.length - 1].end,
      text,
      words: segmentWords,
    };
  });
  const words = segments.flatMap(segment => segment.words);

  await page.route(/http:\/\/127\.0\.0\.1:8642\/.*/, async route => {
    const pathname = route.request().url().replace('http://127.0.0.1:8642', '').split('?')[0];
    if (pathname === '/transcription/engines') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          default_engine: 'faster-whisper',
          default_model: 'smart',
          recommended_language: 'ru',
          engines: {
            'faster-whisper': {
              available: true,
              selectable: true,
              default_model: 'smart',
              label: 'ScriptCut Smart Transcript',
            },
          },
        }),
      });
    }
    if (pathname === '/system/checks') {
      const ready = label => ({ ok: true, label, detail: 'Ready' });
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ready',
          checks: {
            backend: ready('Local backend'),
            python: ready('Python'),
            ffmpeg: ready('FFmpeg'),
            captions: ready('Burn-in captions'),
            transcription: ready('Transcription'),
            audio: ready('Studio Sound'),
            background: ready('Background removal'),
          },
        }),
      });
    }
    if (pathname === '/background/capabilities') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          available: false,
          models: [],
          devices: [],
          message: 'Synthetic QA fixture',
        }),
      });
    }
    if (pathname === '/jobs/transcribe') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'demo' }),
      });
    }
    if (pathname === '/jobs/demo') {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'succeeded',
          progress: 100,
          message: 'Smart Transcript готов',
          result: {
            words,
            segments,
            language: 'ru',
            engine: 'faster-whisper',
            model: 'small',
            requested_model: 'smart',
          },
        }),
      });
    }
    if (pathname === '/audio/waveform') {
      const peaks = Array.from({ length: 1200 }, (_, index) => {
        const phrase =
          Math.abs(Math.sin(index / 17)) * 0.38 +
          Math.abs(Math.sin(index / 43)) * 0.28 +
          Math.abs(Math.sin(index / 7)) * 0.12;
        const silenceGate = index % 173 > 142 ? 0.14 : 1;
        const power = Math.min(0.92, 0.06 + phrase * silenceGate);
        return [-power, power];
      });
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ duration: 40, peaks }),
      });
    }
    if (pathname === '/file') {
      return route.fulfill({
        status: 200,
        contentType: 'video/mp4',
        path: '/Users/alice/Documents/streams/.impeccable/mocks/scriptcut-demo-media.mp4',
      });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });

  await page.reload();
  await page.getByRole('button', { name: 'Открыть полный стрим' }).click();
  await page.waitForTimeout(1200);
  const firstApply = page.getByRole('button', { name: 'Применить', exact: true }).first();
  if (await firstApply.isVisible()) await firstApply.click();
  await page.locator('[data-word-index="19"]').click();
  await page.waitForTimeout(300);
}
