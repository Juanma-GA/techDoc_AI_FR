---
name: one-pager-ppt
description: "Use when: creating an editable PowerPoint one-pager for a repository POC from a supplied PPTX template, preparing one-pager content, or validating a generated one-pager deck. Do not use for: inventing product claims, modifying the source template, reading user documents or databases, or generating a PPTX without explicit confirmation."
---

# One-Pager PowerPoint

## Purpose And Non-Goals

Create one client-ready `.pptx` containing exactly two editable slides for a repository POC by filling a supplied PowerPoint template: slide 1 in French and slide 2 in English. Preserve the template layout and visual identity while grounding claims in repository evidence. Each slide must be directly reusable in an existing deck.

This skill does not redesign the template, certify a product, invent capabilities, or turn screenshots into flattened slides.

## Expected Inputs

- POC slug or repository path.
- Source `.pptx` template path.
- Application-local output path under `apps/<slug>/one-pager/`.
- French and English presentation content.
- Optional paths to two approved screenshots.
- Optional JSON mapping when the template does not use the standard shape names.
- Explicit confirmation immediately before creating or replacing the output file.

The standard editable shape names are:

`ONEPAGER_MAIN_TITLE`, `ONEPAGER_SECTION_TITLE`, `ONEPAGER_APP_NAME`, `ONEPAGER_STATUS`, `ONEPAGER_CHALLENGE`, `ONEPAGER_SOLUTION`, `ONEPAGER_FEATURES`, `ONEPAGER_SCREENSHOT_TOP`, `ONEPAGER_SCREENSHOT_BOTTOM`, `ONEPAGER_CALLOUT_1`, `ONEPAGER_CALLOUT_2`, `ONEPAGER_CALLOUT_3`, `ONEPAGER_LOCAL_SECURITY`, `ONEPAGER_SHARED_SECURITY`, and `ONEPAGER_FOOTNOTE`.

## Normative Documents

1. Current external AACF when an AACF compliance claim is requested and the source is accessible.
2. `STANDARD_POC.md` for local technical, security, deployment, and product constraints.
3. `CLAUDE.md` for repository method and data-safety rules.
4. The target application's README, source code, tests, and technical reference.
5. The supplied PowerPoint template for visual layout only; it is not evidence for product claims.

If current AACF content cannot be reached, state `AACF NON VERIFIABLE` and omit AACF compliance claims.

## Procedure

1. Confirm the target POC, template, language, output, screenshots, and intended audience.
2. Inspect only source code, configuration, tests, and documentation needed to establish the tool's purpose, features, limitations, security posture, and maturity.
3. Separate confirmed capabilities from limitations and unverified behavior. Never promote a POC to production-ready, certified, or fully compliant without explicit evidence.
4. Draft equivalent French and English content for challenge, solution, three to five features, three callouts, local security, shared on-premise security, and a visible limitation footnote when needed.
5. Inspect the template with:
   `python .github/skills/one-pager-ppt/scripts/generate_one_pager.py inspect --template <template.pptx>`
6. If the supplied corporate deck contains the reference design rather than tagged template slides, extract the approved French and English reference slides with `build_reference_template.py`. Never approximate an available corporate reference with a synthetic layout.
7. If the standard shape names are absent, propose a mapping JSON from content keys to existing shape names. Do not modify the source corporate deck.
8. Create or update `apps/<slug>/one-pager/content.json`, with `fr` and `en` objects and shared screenshot paths. Screenshot paths may be omitted; placeholders then remain visible and generation reports them.
9. Set the output to `apps/<slug>/one-pager/<slug>-one-pager-fr-en.pptx`. Never place a final deliverable in the repository root, the session folder, or another application's directory.
10. Present the final claims, exact application-local output path, source template path, missing screenshots, and command. Request explicit confirmation.
11. After confirmation, generate with:
   `python .github/skills/one-pager-ppt/scripts/generate_one_pager.py generate --template <template.pptx> --content <content.json> --output <output.pptx> [--mapping <mapping.json>]`
12. Reopen the generated deck and verify that it contains exactly two slides in the order FR then EN, both slides are readable, required shapes were filled, screenshots were inserted or reported missing, and all objects remain editable.
13. Report executed checks separately from recommended visual review in Microsoft PowerPoint.

## Optional Capabilities And Fallbacks

- Without Python or `python-pptx`, return the final content JSON, mapping instructions, exact generation command, and mark PPTX generation unexecuted.
- Without write permission or confirmation, stay in preview mode and return the proposed content and output path.
- Without screenshots, preserve the template placeholders and clearly report `SCREENSHOTS NOT PROVIDED`.
- Without standard shape names, use `inspect` and a mapping JSON. If shapes cannot be mapped unambiguously, stop and ask the user.
- Without current AACF access, omit AACF verdicts and report `AACF NON VERIFIABLE`.

## Validations

- YAML frontmatter parses and the folder name matches `name`.
- The source template exists, is a `.pptx`, and is never overwritten.
- Content and generated PowerPoint are stored under the target application's `apps/<slug>/one-pager/` directory.
- Both `fr` and `en` content objects contain every required text field, three callouts, and three to five features.
- Every mapped shape exists on the selected slide.
- Screenshot files, when supplied, are supported images and are inserted into the original placeholder bounds.
- The generated file reopens with exactly two editable slides ordered FR then EN; non-targeted template elements are preserved on both.
- No visible claim exceeds the evidence found in the repository.
- No personal path, secret, user document, database, upload, or generated personal data is embedded.
- A human visual review checks overflow, arrow alignment, image cropping, and brand fidelity.

## Expected Output

- `apps/<slug>/one-pager/<slug>-one-pager-fr-en.pptx`, containing exactly two standalone editable slides: French first, English second.
- `apps/<slug>/one-pager/content.json`, containing the structured bilingual content used to generate it.
- A concise generation report containing evidence sources, executed validations, unresolved placeholders, unverified claims, and the output path.

## Limits And Unverified States

Automated checks cannot guarantee visual quality, font availability, or exact text overflow behavior across PowerPoint versions. The result requires a final human visual review. Generated S1000D wording must describe best-effort skeleton generation unless stronger behavior has been independently validated.

## Safety And Data Handling

Never read or embed application databases, user storage, uploads, source documents, secrets, API keys, or generated personal data. Use only approved screenshots that contain no sensitive information. Do not overwrite the source template or an existing output without explicit confirmation. Do not install dependencies, create files, or generate the PPTX without the required mutation approval.
