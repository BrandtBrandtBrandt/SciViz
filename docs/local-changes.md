# Changes after the hosted snapshot

Imported 17 November 2026 from Hugging Face Space revision `899550f08780fe3dbdc5cb6439e81010cf04888d`. The initial file hashes are recorded in `source-snapshot.json`.

## Article-reading fix

A user selected Quanta's “A New Era for the Dawn of Life” (`https://www.quantamagazine.org/a-new-era-for-the-dawn-of-life-20261112/`) through the website's random picker. Its outer HTML contains a `full-size-interactive` iframe rather than an extractable article body. The old reader correctly rejected the empty article text, but the picker should not have offered this page as a readable article.

Changes:

- Filter multimedia, interactive and podcast categories from the RSS candidate pool.
- Check candidate readability before returning a randomly selected URL, trying at most three candidates.
- Give explicitly pasted interactive features a specific message recommending another article or a public abstract.
- Keep hostname validation, redirect checks, DNS pinning and response-size limits intact. Embedded applications are not fetched or executed.

These changes use article HTTP requests only, not model inference or GPU checks. The two article modules were published to the existing Hugging Face Space on 17 November 2026 as revision `bbd649a17f6a59cf5b79a76517c0b245cbd45d10`, after explicit approval. No README, UI, dependency, model or hardware changes were deployed. See `article-fix-release.json` for release evidence. No automatic Space or portfolio deployment is configured in this repository.
