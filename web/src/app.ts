const root = document.querySelector<HTMLElement>('[data-sciviz]');
if (root) initialise(root);

function initialise(root: HTMLElement) {
  const get = <T extends HTMLElement>(selector: string) => {
    const element = root.querySelector<T>(selector);
    if (!element) throw new Error(`Missing SciViz element: ${selector}`);
    return element;
  };
  const open = get<HTMLButtonElement>('[data-open]');
  const panel = get<HTMLElement>('[data-panel]');
  const workspace = get<HTMLElement>('.sciviz-workspace');
  const form = get<HTMLFormElement>('form');
  const url = get<HTMLInputElement>('[name="article"]');
  const abstract = get<HTMLTextAreaElement>('[name="abstract"]');
  const submit = get<HTMLButtonElement>('[type="submit"]');
  const cancel = get<HTMLButtonElement>('[data-cancel]');
  const status = get<HTMLElement>('[role="status"]');
  const result = get<HTMLElement>('[data-result]');
  const titleColours = ['#1d324d', '#4f6465', '#69516d', '#805047', '#526344', '#6d5840'];
  let titleColourIndex = -1;
  const image = get<HTMLImageElement>('[data-image]');
  const video = get<HTMLVideoElement>('[data-video]');
  const imageResult = get<HTMLElement>('[data-image-result]');
  const videoResult = get<HTMLElement>('[data-video-result]');
  const titleLinks = [...root.querySelectorAll<HTMLAnchorElement>('[data-title-link]')];
  const titleTexts = [...root.querySelectorAll<HTMLElement>('[data-title-text]')];
  const imageDownload = get<HTMLAnchorElement>('[data-image-download]');
  const videoDownload = get<HTMLAnchorElement>('[data-video-download]');
  const random = get<HTMLButtonElement>('[data-example]');
  const deterministic = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  random.textContent = deterministic ? 'Use the birdsong reference' : 'Choose a random Quanta article';
  const quotaHelp = get<HTMLElement>('[data-quota-help]');
  let generation = 0;
  let activeJob: {cancel: () => Promise<void>} | null = null;
  const message = (text: string, busy = false) => {
    status.textContent = text;
    status.classList.toggle('is-busy', busy);
    submit.textContent = busy ? 'Generating…' : 'Generate visual';
  };
  let layoutAnimation: Animation | null = null;
  let workspaceAnimation: Animation | null = null;
  function changeLayout(expanded: boolean) {
    layoutAnimation?.finish();
    workspaceAnimation?.finish();
    const before = root.getBoundingClientRect().height;
    const previous = workspace.getBoundingClientRect();
    video.pause();
    panel.hidden = !expanded;
    open.hidden = expanded;
    open.setAttribute('aria-expanded', String(expanded));
    root.classList.toggle('is-open', expanded);
    const after = root.getBoundingClientRect().height;
    const next = workspace.getBoundingClientRect();
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      layoutAnimation = root.animate(
        [{height: `${before}px`}, {height: `${after}px`}],
        {duration: 550, easing: 'cubic-bezier(.22,1,.36,1)'},
      );
      workspaceAnimation = workspace.animate(
        [{width: `${previous.width}px`, transform: `translate(${previous.left-next.left}px, ${previous.top-next.top}px)`},
         {width: `${next.width}px`, transform: 'translate(0, 0)'}],
        {duration: 550, easing: 'cubic-bezier(.22,1,.36,1)'},
      );
    }
  }
  open.addEventListener('click', () => {
    changeLayout(true);
    url.focus({preventScroll: true});
  });
  get<HTMLButtonElement>('[data-close]').addEventListener('click', () => {
    changeLayout(false);
    open.focus({preventScroll: true});
  });
  random.addEventListener('click', async () => {
    if (submit.disabled) return;
    // One build: loopback previews are reproducible; deployed demos vary.
    if (deterministic) {
      url.value = 'https://www.quantamagazine.org/what-can-birdsong-teach-us-about-human-language-20241121/';
      abstract.value = '';
      message('Birdsong reference selected. Choose Generate visual to compare this version.');
      submit.focus();
      return;
    }
    const current = ++generation;
    random.disabled = true;
    submit.disabled = true;
    cancel.hidden = false;
    message('Finding a recent Quanta article…', true);
    try {
      const {Client} = await import('@gradio/client');
      const client = await Client.connect('BrandtBrandtBrandt/sciviz', {credentials: 'omit'});
      if (current !== generation) return;
      const response = await client.predict('/random_article', [url.value.trim()]);
      if (current !== generation) return;
      if (!Array.isArray(response.data)) throw new Error('Could not get an article. Paste a Quanta URL instead.');
      const article = response.data[0] as {status?: string; title?: string; url?: string; detail?: string};
      if (article.status !== 'ready' || !article.url || !article.title) {
        throw new Error(article.detail || 'Could not get an article. Paste a Quanta URL instead.');
      }
      const selected = new URL(article.url);
      if (selected.protocol !== 'https:' || !['www.quantamagazine.org', 'quantamagazine.org'].includes(selected.hostname)) {
        throw new Error('The article link was not recognised. Paste a Quanta URL instead.');
      }
      url.value = selected.href;
      abstract.value = '';
      message(`Selected: “${article.title}” — choose Generate visual to begin.`);
      submit.focus();
    } catch (error) {
      if (current === generation) message(error instanceof Error ? error.message : 'Could not get an article. Paste a Quanta URL instead.');
    } finally {
      random.disabled = false;
      if (current === generation) { submit.disabled = false; cancel.hidden = true; }
    }
  });
  cancel.addEventListener('click', async () => {
    ++generation;
    const job = activeJob;
    activeJob = null;
    submit.disabled = false;
    cancel.hidden = true;
    message('Cancelled.');
    try { await job?.cancel(); } catch { /* Local cancellation remains effective. */ }
  });
  function fileUrl(value: unknown): string | null {
    if (!value || typeof value !== 'object') return null;
    const item = value as {url?: unknown; video?: unknown};
    if (item.video) return fileUrl(item.video);
    if (typeof item.url !== 'string') return null;
    const candidate = new URL(item.url, 'https://brandtbrandtbrandt-sciviz.hf.space');
    return candidate.origin === 'https://brandtbrandtbrandt-sciviz.hf.space' && candidate.pathname.startsWith('/gradio_api/file=') ? candidate.href : null;
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    if (Boolean(url.value.trim()) === Boolean(abstract.value.trim())) {
      message('Enter an article URL or an abstract. Use one source at a time.');
      url.focus(); return;
    }
    if (url.value.trim()) {
      const candidate = new URL(url.value.trim());
      if (candidate.protocol !== 'https:' || candidate.username || candidate.password || candidate.port ||
          !['quantamagazine.org', 'www.quantamagazine.org', 'arxiv.org', 'www.arxiv.org'].includes(candidate.hostname)) {
        message('Use a Quanta Magazine or arXiv URL, or paste a public abstract instead.');
        url.focus(); return;
      }
    }
    const current = ++generation;
    quotaHelp.hidden = true;
    // One colour per result pair; consecutive generations use different colours.
    const colourStep = titleColourIndex < 0 ? 0 : 1;
    titleColourIndex = (Math.max(titleColourIndex, 0) + colourStep +
      Math.floor(Math.random() * (titleColours.length - colourStep))) % titleColours.length;
    result.style.setProperty('--sciviz-title-background', titleColours[titleColourIndex]);
    submit.disabled = true;
    cancel.hidden = false;
    result.hidden = true;
    video.pause(); video.removeAttribute('src'); video.removeAttribute('poster');
    image.removeAttribute('src');
    imageResult.hidden = true;
    videoResult.hidden = true;
    imageDownload.hidden = true;
    videoDownload.hidden = true;
    for (const link of titleLinks) { link.hidden = true; link.removeAttribute('href'); link.textContent = ''; }
    for (const text of titleTexts) { text.hidden = false; text.textContent = ''; }
    message('Connecting to SciViz. Free hosting may need a moment to wake up…', true);
    try {
      const {Client} = await import('@gradio/client');
      const client = await Client.connect('BrandtBrandtBrandt/sciviz', {credentials: 'omit'});
      if (current !== generation) return;
      const job = client.submit(deterministic ? '/generate_reference' : '/generate', [url.value.trim(), abstract.value.trim()]);
      activeJob = job;
      for await (const event of job) {
        if (current !== generation) break;
        if (event.type === 'status') {
          if (event.stage === 'error') throw new Error('Free generation is currently unavailable. Please try later or explore the examples below.');
          if (event.stage === 'pending') message('Waiting for free capacity. You can keep exploring the article while SciViz works.', true);
          continue;
        }
        if (event.type !== 'data' || !Array.isArray(event.data)) continue;
        const [rawMeta, imageData, videoData] = event.data;
        const meta = rawMeta as {api_version?: number; message?: string; phase: string; code?: string; title?: string; source_url?: string} | null;
        if (!meta || meta.api_version !== 1 || typeof meta.phase !== 'string') throw new Error('SciViz returned an unfamiliar response. Please try later.');
        message(meta.message || 'Generating…', !['complete', 'error'].includes(meta.phase));
        quotaHelp.hidden = meta.code !== 'quota_exhausted';
        let sourceUrl: URL | null = null;
        try {
          const candidate = new URL(meta.source_url || '');
          if (candidate.protocol === 'https:' && !candidate.username && !candidate.password &&
              ['www.quantamagazine.org', 'quantamagazine.org', 'arxiv.org', 'www.arxiv.org'].includes(candidate.hostname)) sourceUrl = candidate;
        } catch { /* Pasted abstracts have no source link. */ }
        const articleTitle = meta.title || 'Scientific visual';
        for (const link of titleLinks) {
          link.textContent = articleTitle;
          link.hidden = !sourceUrl;
          if (sourceUrl) link.href = sourceUrl.href; else link.removeAttribute('href');
        }
        for (const text of titleTexts) { text.textContent = articleTitle; text.hidden = Boolean(sourceUrl); }
        const illustration = fileUrl(imageData);
        if (illustration) {
          result.hidden = false;
          if (image.src !== illustration) image.src = illustration;
          imageResult.hidden = false;
          imageDownload.href = illustration; imageDownload.hidden = false;
          video.poster = illustration;
        }
        const film = fileUrl(videoData);
        if (film && video.src !== film) {
          result.hidden = false;
          video.src = film; videoResult.hidden = false;
          video.muted = true;
          if (!panel.hidden && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
            void video.play().catch(() => { /* Native controls remain available. */ });
          }
          videoDownload.href = film; videoDownload.hidden = false;
        }
      }
    } catch (error) {
      if (current === generation) message(error instanceof Error ? error.message : 'SciViz is unavailable. Please try later.');
    } finally {
      if (current === generation) { activeJob = null; submit.disabled = false; cancel.hidden = true; }
    }
  });
}
