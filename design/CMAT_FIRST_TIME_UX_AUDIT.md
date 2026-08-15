# CMAT First-Time User / UX Research Audit

**Scope.** First-time researcher experience for the Windows desktop build.

## Evidence and limits

| Label | Meaning |
|---|---|
| **Observed** | I launched `dist/CMAT/CMAT.exe`; the process opened responsively with the title **Children's Media Analysis Toolkit (CMAT)**. The environment did not allow persistent desktop clicking, so I could not execute dialogs or analyze a video through the GUI. |
| **User-reported intent** | The requested launch experience is the **Pipeline** page first. |
| **Code-supported** | UI labels, available actions, state transitions, exports, manifests, and warnings were traced in `gui.py`, `gui_sampler.py`, `gui_pipeline.py`, and the analyzer modules. |
| **Inference** | A likely first-time-user reaction based on the visible labels and documented behavior. It is not claimed as direct observation. |

This is therefore a serious *inspection-led first-use audit*, not a usability study with recruited researchers. The app does have an impressive amount of research functionality; the central UX risk is that it exposes a capable research system as several distinct tools whose relationship must be inferred.

## Executive assessment

CMAT most clearly communicates **Model C: Show -> Episodes -> Metadata -> Analysis -> Aggregate -> Visualization**, with a competing engineer/tool model layered on top: **Library -> tabs -> dialogs -> cache/index**. It partially supports Model A (**Research Question -> Corpus -> Sample -> Analysis -> Results -> Export**) through the Pipeline view and Episode Sampler, but this is not yet the dominant, unmistakable route. Model B (**Videos -> Analyze -> Browse -> Compare -> Export**) is reasonably supported for a few existing files.

For research users, Model A should be the primary first-run mental model, while Models B and C should be deliberately offered as alternate entry routes. A researcher should choose a workflow first, not discover it by noticing a sampler button beside general Settings.

There is an important implementation/intent mismatch: the supplied requirement says the Pipeline page should appear first. The checked-in `App.__init__` selects **Library** when no root folder exists. If the distributed build instead opens Pipeline, preserve that behavior and test it; if it opens Library, this is a high-priority onboarding defect because the intended research-roadmap entry point is bypassed.

## Five realistic research scenarios

| Scenario | Researcher and question | Media in hand | Desired output | Expected CMAT areas |
|---|---|---|---|---|
| 1. Undergraduate study | Maya, a senior running a child-viewing study: do three preschool programs differ in pacing, motion, and language complexity? | 60 legally obtained MP4 episodes in three show folders; some subtitles; little software experience. | Defensible 30-episode sample, episode-level CSV, methods record, figures for thesis. | Pipeline, Library, Episode Sampler, Analyze, Language, results, CSV/PDF export. |
| 2. PBS portfolio researcher | Jordan compares six programs across several seasons to guide a descriptive internal research report, not child-level recommendations. | Hundreds of episodes, uneven season counts, production metadata, many SRTs. | Standardized cross-show data, batch results, season trends, comparison charts. | Library/index, batch analysis, metadata import, aggregates, charts, filtering, exports. |
| 3. Historical researcher | Dr. Alvarez asks whether formal features changed from 1992–2025. | Decades of episodes with irregular filenames; air dates are incomplete. | Date-linked panel dataset, era definitions, documented treatment of missing dates, longitudinal plots. | Metadata import/editing, sampler, index, series aggregate, charts, eras, CSV export. |
| 4. Linguist | Priya studies dialogue complexity and already has SRT/VTT files. | Caption files for 80 episodes; video may be absent or irrelevant. | Subtitle-level lexical/readability table and charts; optionally WPM/density where video/runtime is available. | Language > Vocabulary, Language > Speech, optional norms/dependencies, CSV export. |
| 5. Research lab corpus | A lab manager coordinates a 1,000-episode corpus, multiple coders, reproducible sampling, and automated-vs-human validation. | Network-managed files, metadata registry, selected samples, coding sheets, analysis outputs. | Auditable sample manifests, provenance-aware dataset, validation reports, collaboration-safe export package. | Sampler, pipeline, queue, index, trials, human coding, validation, agreement, exports. |

## Walkthroughs

### 1. Undergraduate children's-media researcher

| Step | First-time journey | Finding / severity | Concrete improvement |
|---|---|---|---|
| 1 | **Goal:** understand what CMAT does and begin a study. **Sees:** intended Pipeline page; elsewhere the app has Library, Automated coding, Human coding, Trials, right-hand Results, plus toolbar Settings/Sampler. **Likely click:** a pipeline stage or `Choose Folder`. | **High.** Pipeline is the right conceptual object, but a blank/default graph editor with `Manage`, `Add`, `Delete`, `Undo`, and `Fit` risks reading as a workflow-designer rather than a guided research plan. The code calls it “Pipeline” and “Analysis Pipeline,” not “Research workflow.” | Make the default Pipeline a non-editing **Start a research workflow** dashboard. Present three large choices: **Analyze a few episodes**, **Create a reproducible sample**, **Analyze a complete corpus**; keep graph editing under `Customize workflow`. |
| 2 | **Goal:** add the three shows. **Sees:** `Choose Root Folder...`, a root-folder instruction, then Library tree. **Likely click:** select the folder containing the MP4s or select a show folder. | **Medium.** Code-supported dialog explicitly says select the parent containing show folders; this is good. But it conflicts with the sampler’s separate “Entry root folder,” and README allows category/season patterns. A novice has to know their directory *is* a study population. | In the chooser, show a compact preview after selection: `3 shows / 60 episodes / 4 seasons detected` and provide **Change layout / Continue**. Rename root folder in research UI to **Media library (contains show folders)**. |
| 3 | **Goal:** decide whether to analyze all 60 or sample 30. **Sees:** `Episode Sampler...` beside Settings and the instruction “optional.” **Likely click:** Analyze Show (Batch), because it is immediate and sampling sounds specialized. | **High.** The main research decision is framed as optional tool choice, rather than a decision about the population, sampling frame, and inferential claim. An undergraduate may batch-analyze first, then mistakenly call the analyzed union a sample. CMAT later warns that all-analyzed aggregates are not designed samples, but that warning arrives too late. | Before first batch analysis, ask: **Is this your complete population or a study sample?** Choices: `Analyze census`, `Create documented sample`, `I am exploring`. Explain consequences and link to manifest creation. |
| 4 | **Goal:** create a 30-episode representative sample. **Sees:** a long Sampler window with nine numbered sections: Input; Stratification (Axis A); Selection method (Axis B); allocation; sort/seed; preview; load/export. Defaults are season + spread/chunked + equal allocation + seed 42. **Likely click:** retain defaults and Preview. | **Medium.** This is unusually well structured and tooltips exist, but “Axis A/B,” “spread/chunked,” “D'Hondt,” and the default seed 42 are statistical concepts introduced before the user states the study design. A default is easily mistaken for a recommendation appropriate to all questions. | Add a 60-second **sampling decision helper** above advanced controls: `Do you need every episode?`, `Should every season be represented?`, `Do you need statistical generalization?` It sets defaults and writes plain-language rationale into the manifest. |
| 5 | **Goal:** analyze the selected episodes. **Sees:** `Send Sample to CMAT`, destination choices `Automated analysis queue`, `Hand-coding worklist`, or `Both`; then an Analysis Queue in a different tab. **Likely click:** Send to automated queue, then look for a Run button. | **High.** “Send” describes routing, not the analysis state or next required action. The queue is separated from the sampler, and a novice may expect selection to start analysis. | Rename primary action to **Add sample to analysis queue — next: Start analysis**. On completion, switch to Analyze and show `30 queued; Start 30 analyses` as the single primary action. Persist a visible queue-to-manifest link. |
| 6 | **Goal:** understand results. **Sees:** a results panel with raw metrics, sensory-load score, component values, later provenance, and Help > About metrics. **Likely click:** treat a higher score as “more harmful/stimulating.” | **High scientific-communication risk.** CMAT’s documentation and About dialog explicitly say stimulus, not child, and not a verdict; that is a major strength. But this essential limitation is not necessarily visible at the moment the composite becomes salient. Age-labelled presets (`Toddler`, `Preschool`) further invite an appropriateness interpretation. | Put a persistent one-line result header beside every composite: **Stimulus profile—not a child outcome or appropriateness rating.** Add `Why this score?` expanding to raw measures → normalized values → weights → score, including preset/date/settings fingerprint. Rename age presets to **reference ranges for studies of…**, with a methodological warning. |
| 7 | **Goal:** use data in R/SPSS and write methods. **Sees:** File export commands activate only when results are current; CSV export creates a provenance sidecar; sampler can export `selected.csv`, `manifest.json`, `worklist.txt`. **Likely click:** export the current show, expecting all selected episodes. | **High.** Exports are contextual to the currently selected result, not a clearly named research dataset. A user can export one show or an aggregate while believing they exported their study sample. | Add **Export research dataset** in Pipeline/Trials, scoped explicitly to `This manifest / This library / Current filter`, with an export review showing episode count, failures, missing metadata, preset/fingerprint groups, and included files. |

**I would get stuck here:** after `Send Sample to CMAT`. The user wants “run my sample,” sees routing and a separate queue, and cannot infer whether analysis has started. Their most likely retry is clicking Send again; that risks duplicate queue entries or uncertainty. Resolve with a post-send handoff and a queue CTA that includes counts and progress.

**Happy path:** `Start research study` → `Add media library` → `Create representative sample` → `Preview + name + lock manifest` → `Analyze sample` → `Review components and data-quality flags` → `Export sample dataset + methods bundle`.

### 2. PBS / children's television researcher

| Step | First-time journey | Finding / severity | Concrete improvement |
|---|---|---|---|
| 1 | **Goal:** define a comparable six-show corpus. **Sees:** a Library tree that derives shows from folder structure, category folders, and recognized season folders. **Likely click:** import top-level root and use show folders. | **Medium.** The folder convention is efficient for a solo user but makes filesystem hierarchy a scientific data model. The app does not first ask whether folders encode show, season, category, or source. | Add a **Library import review** that labels detected units and permits editing `Show`, `Season`, and `Category` before analysis. Save an import map. |
| 2 | **Goal:** analyze hundreds of episodes. **Sees:** select show then `Analyze Show (Batch)`; queue/progress; cache behavior. **Likely click:** batch each show. | **Medium.** The action is easy to discover. The cost, skipped/cached count, stale settings status, and cross-show standardization requirement are less front-loaded. | Batch confirmation should state `N new / M cached / K stale`, expected analysis time, active measurement fingerprint, subtitle/Whisper status, and a **Use same settings for all selected shows** option. |
| 3 | **Goal:** attach comparable air-date/season metadata. **Sees:** manual fields only after selecting an analyzed episode; separate File dialogs for TVMaze and Wikipedia. **Likely click:** TVMaze import. | **Medium.** The capabilities are good, including matching previews, but their placement after analysis and reliance on filename matching can lead to undetected partial matches. | Promote **Metadata completeness** to the pipeline/dashboard. Require a review screen: matched, ambiguous, unmatched, overwritten, and source/provenance; make applying changes reversible. |
| 4 | **Goal:** compare shows/seasons. **Sees:** Index table, filter, sort, show aggregate, full-series aggregate, Pin/Compare, charts. **Likely click:** pin an episode then compare another, or click a show aggregate. | **High.** “Pin for Compare” naturally sounds episode-to-episode. It is not a clear route to a six-show comparison. Full Series Aggregate is discoverable only in Analyze and sounds like a computational object rather than a study result. | Add a **Compare cohorts** workspace: choose shows/samples, declare matching settings, select metrics, and generate table/chart/export. Rename `Full Series Aggregate` to **All-seasons summary for this show** and display what is included. |
| 5 | **Goal:** export a standardized analytical dataset. **Sees:** results export and index, with hidden context. **Likely click:** filter index, then File > export. | **High.** Index filtering may be perceived as defining an export cohort, yet exports follow current result selection instead. | Put `Export filtered index (N episodes)` next to Filter. Include one row per episode, a data dictionary, settings/provenance columns, and a failure/missingness report. |

**I would get stuck here:** moving from “six analyzed shows” to “one comparable dataset.” The likely action—export each show one at a time—works technically but makes merging/provenance reconciliation an external, error-prone task. A cohort export solves it.

**Happy path:** `Import corpus` → `standardize detected structure + metadata` → `choose a shared measurement protocol` → `batch analyze cohort` → `resolve failures/staleness` → `compare cohort` → `export one analysis-ready dataset`.

### 3. Historical / longitudinal researcher

| Step | First-time journey | Finding / severity | Concrete improvement |
|---|---|---|
| 1 | **Goal:** ingest irregular multi-decade episodes. **Sees:** root-folder tree and season auto-detection based on names such as Season/Series/S/Part. **Likely click:** organize folders/names until recognized. | **High.** The research unit should not depend on filesystem naming conventions, especially for historical holdings and multipart episodes. | Support a registry-first import (`filepath`, show, season, episode, title, air date, source ID) as a first-class library workflow, not just an alternative inside Sampler. |
| 2 | **Goal:** establish dates and episode order. **Sees:** post-analysis manual `Air Date / Season / Ep #` fields; TVMaze/Wikipedia import. **Likely click:** use an importer, then manually patch gaps. | **High.** The workflow makes metadata an after-analysis appendage although it determines sampling/chronology. An imported date's source and confidence are not prominent in the ordinary index workflow. | Add a **Metadata stage** before analysis with a completeness meter and provenance columns: source, imported date, review state, ambiguity. |
| 3 | **Goal:** define eras, visualize trends. **Sees:** `Show Chart`, X-axis Air Date only when >=80% dated, color by Season/Era, `Edit Eras…`. **Likely click:** chart then discover eras. | **Medium.** The 80% threshold and fallback are sensible but can feel like a missing feature; “Era” is a research concept without a definition or shared convention. | In chart setup, explain `Air Date unavailable: 54/100 episodes dated; need 80%` and offer `Chart dated subset`, `Use episode number`, `Complete metadata`. Define era as a user-defined date range and surface unassigned episodes. |
| 4 | **Goal:** report changes over time without overclaiming. **Sees:** descriptive chart controls, aggregate stats, export. **Likely click:** export visual/table. | **Medium.** Charts support exploration but do not foreground missingness, settings consistency, sample design, or whether dates came from metadata imports. | Add a longitudinal export/chart caption template: `N episodes; date coverage; metric/preset; analysis fingerprint; sample rule; unassigned era count`. |

**I would get stuck here:** when Air Date is not selectable. The researcher wants a time plot, sees an unavailable/fallback axis but may not know whether the cause is no dates, parse failure, or an 80% gate. Make the failure state diagnostic and actionable.

**Happy path:** `Import registry/library` → `review metadata and date coverage` → `define corpus or stratified sample` → `lock protocol` → `analyze` → `define eras` → `chart with coverage disclosure` → `export panel data + figure provenance`.

### 4. Language / linguistic researcher

| Step | First-time journey | Finding / severity | Concrete improvement |
|---|---|---|
| 1 | **Goal:** analyze existing SRT/VTT files, perhaps without video. **Sees:** Language is nested under `Automated coding`; Speech and Vocabulary are sub-tabs. **Likely click:** Automated coding > Language > Vocabulary. | **Medium.** The route is reachable, but the product initially presents itself as sensory/video analysis. A linguist may never infer that Vocabulary accepts caption files directly. | First-run workflow choice must include **Analyze subtitles/language**. Give Language its own top-level entry or an explicit Pipeline branch. |
| 2 | **Goal:** understand Speech vs Vocabulary. **Sees:** Speech table begins “Choose a root folder, then click Refresh”; Vocabulary has `Browse CC Files…`, `Browse Folder…`, `Analyze`. **Likely click:** Vocabulary for lexical metrics, Speech for WPM/density. | **Medium.** This distinction is technically sound but unnamed: Speech metrics need episode duration and subtitle timing; Vocabulary is direct-file analysis. Blank values may look like failure rather than a different input path. | Add a two-card explainer: **Speech timing (WPM, density): video episode + timed captions/Whisper**; **Text complexity (readability, tiers, AoA, MTLD): SRT/VTT files**. Give each blank cell a reason and next action. |
| 3 | **Goal:** use Whisper if captions are missing. **Sees:** Settings has auto-transcription/model and Analyze has `Transcribe Missing Subtitles`; optional tools also exist. **Likely click:** search Settings, perhaps expect transcription when opening Language. | **High.** Whisper's relationship to automatic episode analysis, the need for videos, model download/compute cost, saved SRT side effect, and re-analysis requirement are dispersed. The code explains some in tooltips/settings, but this is not a coherent first-use flow. | From Speech show `No captions found—choose: add SRT/VTT, transcribe with Whisper, or exclude`. State model/download/disk/time, output location, consent/copyright considerations, and whether it alters raw analysis. |
| 4 | **Goal:** understand missing AoA/concreteness or NLP prerequisites. **Sees:** Vocabulary panel calculates status; README mentions optional norm files and spaCy dependencies. **Likely click:** Analyze and inspect blank results. | **Blocker for source users; High for bundled users if dependencies absent.** A first-time linguist should not need README to discover data/norm dependencies. | On the Vocabulary tab, show dependency cards with `Installed / Missing / Optional`; for each output say `Available`, `Unavailable—install`, or `Unavailable—provide norms`, with a one-click guided action and cited source/licence. |
| 5 | **Goal:** export results. **Sees:** Vocabulary-specific `Export CSV…`; generic File export is contextual to sensory results. **Likely click:** use the green/nearby vocabulary export if noticed. | **Medium.** This is a good direct export, but its scope, schema, file-to-episode linkage, norms/version provenance, and integration with sensory output are not obvious. | Label it **Export vocabulary dataset (N subtitle files)** and provide a data dictionary plus `Join key / source filename / norm coverage / preprocessing version` columns. |

**I would get stuck here:** on blank AoA/MTLD/readability values. The user sees a statistic without knowing whether captions were too short, norms are absent, packages are missing, parsing failed, or the metric is inapplicable. Replace blank with an explicit status and remediation.

**Happy path:** `Start: language study` → `Select captions or caption folder` → `verify dependencies/norm coverage` → `Analyze text` → `optionally link episodes for WPM/density` → `inspect metric definitions/missingness` → `export linguistic dataset`.

### 5. Research lab / large corpus workflow

| Step | First-time journey | Finding / severity | Concrete improvement |
|---|---|---|
| 1 | **Goal:** make library state traceable across researchers. **Sees:** root folder is remembered in `config.json`; cache lives under `<root>/.analysis`; SQLite index is created/backfilled from cache. **Likely click:** share the root on a drive and let each analyst open it. | **High.** This is a hidden distributed-state model. It is unclear which artifacts should be versioned, shared, backed up, or treated as per-user settings. A remembered root can silently reopen a prior corpus. | Add a **Project manifest** at the library root: project ID, root/registry import, schema version, team protocol, active measurement profile, provenance policy. On open, identify the project and show last modifier/time; make per-user preferences separate. |
| 2 | **Goal:** protect comparability. **Sees:** weights/ceilings rescore cached results; raw-measurement settings use a fingerprint and stale warning; toolbar preset can change current display. **Likely click:** adjust presets to explore and later export. | **Blocker for defensible lab dataset.** Even though CMAT tracks fingerprints and warns of staleness, the lab can still have mixed settings/presets, and rescoring from cache changes displayed/indexed interpretation. An easily changed toolbar preset is not a locked protocol. | Add **Measurement protocol** objects that are immutable once a study run begins. Every result/export must carry protocol ID; cohort views refuse or visibly partition mixed fingerprints/protocols. Require an explicit fork to change a protocol. |
| 3 | **Goal:** batch safely and avoid accidental re-analysis. **Sees:** cache behavior and `Remove Stale` index action; results are reused. **Likely click:** rerun batch/clean stale entries as needed. | **High.** “Cached,” “stale,” “remove stale,” and filesystem existence are different states. Removing stale index rows only removes missing-file entries; it does not resolve measurement staleness. | Provide a corpus health dashboard: `missing file`, `new`, `cached/current`, `cached/outdated settings`, `failed`, `metadata incomplete`, `subtitle absent`, with bulk actions and no ambiguous “stale.” |
| 4 | **Goal:** keep sample selection and analysis inseparable. **Sees:** manifest stores method, seed, frame definition, strata, software version; sample aggregate reloads cached paths. **Likely click:** export manifests and later use Trials. | **Medium.** This is a strong foundation. But sample output can be exported separately from queue execution, and aggregate can skip uncached sample paths after warning. The lab may not get a single immutable run record tying selected files to analysis outcomes/settings. | On `Lock and analyze sample`, create a run manifest containing selected file hashes/paths, metadata snapshot, protocol ID/fingerprint, analysis start/end, failures, output checksums, CMAT version/git commit. Never silently substitute path matches. |
| 5 | **Goal:** validate automation against human coding. **Sees:** separate Human coding `Code`, `Validate tool`, `Agreement` and Trials; useful guides, codebooks, detection controls, parameter sweep, audit artifacts. **Likely click:** choose videos and create/open coding sheets. | **Medium.** The functionality is unusually strong, but it reads as a parallel specialist subsystem. The lab needs a declared validation plan: which sample, coder assignments/blinding, train/test split, detector version, and results linked to the production protocol. | Add a **Validation study wizard** that starts from a locked sample and records coder, codebook version, blind status, training/tuning set vs held-out test set, detector profile, and release decision. |
| 6 | **Goal:** hand data to statistical analysts. **Sees:** current-result CSV/JSON/PDF, Vocabulary CSV, sampler files, caches/index. **Likely click:** collect several exports. | **High.** The data model is distributed across exports and local state. There is no obvious “research release package” assembling flat episode data, metadata, sample membership, protocols, validation, readme/data dictionary, and checksums. | Add **Create analysis package**: versioned folder/ZIP with `episodes.csv`, `shows.csv`, `samples.csv`, `metadata.csv`, `protocols.json`, `validation.csv`, `README.md`, `data_dictionary.csv`, and checksums. |

**I would get stuck here:** when a second researcher opens the same corpus. The user wants to know “is this the approved dataset?” but sees a remembered folder, a local config, cache and DB behavior, and separate Trials. The expected action—open root and analyze—works, but the provenance boundary is invisible. A project manifest + corpus health screen is necessary.

**Happy path:** `Open/initialize project` → `import locked registry and protocol` → `validate corpus health` → `draw and lock sample` → `batch analyze run` → `review failures/staleness` → `run validation study` → `create reproducible analysis package`.

## Mental-model audit

| Model | Current support | Assessment |
|---|---|---|
| **A. Research question -> corpus -> sample -> analysis -> results -> export** | Pipeline stages, Sampler manifest, Trials, aggregate warnings, exports. | Correct research model, but not consistently the primary navigation or completion model. |
| **B. Videos -> analyze -> browse -> compare -> export** | Library tree, Analyze Episode/Show, Index, Pin/Compare, contextual export. | Works best for an exploratory one/few-episode user; this is the most immediately actionable UI route. |
| **C. Show -> episodes -> metadata -> analysis -> aggregate -> visualization** | Folder-derived library, metadata fields/import, show/full-series aggregate, charts. | The most strongly communicated data organization. It is sensible for television, but insufficient for sample-based, cross-show, subtitle-only, or lab work. |

**Conclusion:** CMAT should lead with Model A, then route to B or C based on a first-run choice. Model C is right as an internal library representation, not as the only conceptual doorway. “Show folder” must not be the hidden prerequisite for a legitimate research corpus.

## Terminology audit

| Term | New researcher understanding | Problem | Suggested wording/help |
|---|---|---|---|
| Sensory load | Partial | Sounds like a clinical or child-effect verdict. | “Composite stimulus-intensity profile” plus persistent non-verdict note. |
| Formal features | Often not | Scientifically necessary media-research term. | Tooltip: “Structural, content-independent properties: cuts, motion, colour, sound.” |
| Composite score | Usually | Does not reveal weighting/normalization. | “Weighted composite (researcher-configurable)” with component drilldown. |
| Normalization | Often not | Technical but necessary. | “Scale each measure against a reference ceiling before combining.” |
| Preset | Partial | Can imply a validated child recommendation. | “Reference-range profile” and description of intended comparison setting. |
| Ceiling | Partial | Could be confused with a limit/safety threshold. | “Reference maximum used for scaling—not a safety cutoff.” |
| Aggregate | Partial | May hide scope/weighting. | “Summary across N episodes (each episode equally weighted).” |
| Episode Sampler | Mostly | Good name; relation to analysis unclear. | “Create reproducible research sample.” |
| Census | Variable | Scientific necessary term. | “Census: include every episode in the defined population.” |
| Systematic sampling | Variable | Needs ordering/start implications. | “Select every kth episode after a documented start/order.” |
| Spread/chunk sampling | Often not | “Chunk” can sound non-random; default is unexplained. | “Distributed sampling across the run” with plain-language example and inference warning. |
| Stratification | Variable | Necessary but abstract. | “Ensure representation within groups (for example, each season).” |
| Manifest | Often not | Software/developer connotation. | “Sample record (method, seed, population, selected episodes).” Keep manifest as file-format label. |
| Analysis queue | Mostly | Does not say whether it runs automatically. | “Episodes waiting to be analyzed—Start analysis required.” |
| Speech density | Often not | Could mean audio loudness. | “% of runtime containing subtitle/speech segments.” |
| WPM | Mostly | Denominator and source unclear. | “Words per minute during dialogue, using timed captions/Whisper.” |
| MTLD | No, without specialist training | Necessary specialist metric but opaque. | “Lexical diversity (MTLD)” and header tooltip with interpretation/caveat. |
| Age of Acquisition | Partial | Could mean viewer age rather than word norms. | “Typical learned age of words (lexical norm), not viewer age.” |
| Era | Mostly | User-defined boundaries and unassigned cases need clarity. | “Your named date range; user-defined, not automatically inferred.” |
| Pinned comparison | Mostly | Does not communicate type/scope of pinned object. | “Compare this episode/show with another selected item.” |
| Root folder | Partial | General computer term, but research meaning is hidden. | “Media library folder (contains show folders).” |
| Library | Mostly | May imply all files are imported rather than indexed in place. | “Indexed media library; videos remain in their folders.” |
| Cache | Often not | Hidden state can alter results/reanalysis expectations. | “Saved analysis result; reused until raw measurement settings change.” |
| Whisper | Variable | AI name gives no operational consequences. | “Whisper transcription: creates timed subtitles from audio; model download/time required.” |
| Vocabulary tiers | Partial | Tier source/cutoffs and preprocessing unclear. | “Word-frequency tiers (common / cross-domain / rare), based on Zipf frequency.” |

## Onboarding: first 5–10 minutes

What works:

- The intended Pipeline-first entry would be a strong start because it can express a research workflow rather than a file browser.
- The root-folder chooser gives a concrete folder hierarchy and explicitly says not to select the show folder.
- The empty Library guidance gives three short steps and identifies sampling as reproducible/documented.
- The sampler has numbered sections, progressive disclosure, previews, and micro-tooltips.
- The Help > About Metrics dialog and result provenance provide unusually responsible scientific caveats.

Where a new user leaves the app for README or developer help:

1. Deciding which workflow applies: exploration, census, representative sample, historical cohort, subtitle-only, or validation.
2. Knowing whether a folder is a show, category, season, or valid root; how to handle nonstandard file names and multiparts.
3. Knowing what must be prepared before analysis: metadata, captions, measurement settings, presets, optional dependencies/norms.
4. Understanding the sampler defaults and whether a “spread/chunked” sample supports their intended claim.
5. Knowing whether `Send Sample to CMAT` has run the analysis and where to start it.
6. Interpreting composite vs component measures, ceiling/preset dependence, and the non-clinical limitation at result time.
7. Finding the path from many analyzed episodes to one exportable study dataset.
8. Diagnosing language blanks, Whisper readiness, subtitle matching, and vocabulary dependency/norm status.
9. Understanding cache, stale measurement settings, and what change requires reanalysis.
10. Knowing where results, metadata, manifests, trial artifacts, and database records live—and how to recover or undo a mistaken import/change.

## Research workflow audit

### Reproducibility

**Strong, code-supported foundations:** sampling manifests include method, allocation, strata, seed, selected episodes, frame definition, date, notes, and software version. Results carry measurement fingerprints/provenance; stale measurement settings are detected; generic CSV gets a provenance sidecar; Trials discovers study artifacts. These are better than ordinary consumer analysis software.

**Gaps:** a sample manifest is not clearly bound to a particular analysis run, exact file identities/hashes are not foregrounded, configurable composite weights/presets can alter displayed scores, root/index/cache/project boundaries are not explained, and generic exports are contextual rather than protocol-locked. A researcher can determine much of the provenance, but not through one obvious screen/package.

### Data integrity

Primary risks are: filesystem hierarchy silently defining shows/seasons; metadata matching/import ambiguity; remembered root folder; mixed raw-measurement fingerprints; current-display rescoring; stale index vs stale measurement terminology; sample aggregate skipping uncached items after warning; and exporting whichever result happens to be selected. None implies bad engineering—the code actively addresses several—but each is a research-user state-management risk.

### Statistical workflow

CMAT can generate CSV/JSON, charts, per-show/sampled summaries, and subtitle tables. The missing bridge is a declared cohort/dataset artifact. The natural statistical handoff should be a flat episode-level table with stable identifiers, show/season/episode/date metadata, sample membership, raw metrics, derived score/protocol fields, missingness/failure flags, and data dictionary/provenance files. Current contextual export makes this transition too dependent on user memory.

### Scientific interpretation

CMAT’s documented distinction is excellent: it measures stimulus features, exposes components, permits adjustable scoring, states that output is not appropriateness/child harm, and marks unvalidated measurements. The experience should make this distinction visible *before and alongside* scores, not mostly through README, a Help menu, tooltips, or after users already see a high/low score. Age-named presets are particularly likely to be misread as developmental safety classifications.

## Feature discoverability

| Feature | Rating | Why |
|---|---|---|
| Episode Sampler | **Easy to discover** | Toolbar, File menu, empty-library CTA, and Pipeline likely expose it. |
| Batch analysis | **Discoverable with exploration** | Clear once a show is selected, but action is in a different tab from Library. |
| Full Series Aggregate | **Requires documentation** | Label is technical and appears as an action among several Analyze buttons. |
| Sample aggregate | **Requires documentation** | Requires locating a saved manifest after analysis; tooltip is useful but not a natural first-use route. |
| Metadata import | **Requires documentation** | File-menu-only; TVMaze/Wikipedia choices and local matching requirements are specialized. |
| Charts | **Discoverable with exploration** | `Show Chart` is visible after rendering a compatible result, but not a global analysis destination. |
| Eras | **Requires documentation** | Nested under Chart and concept-specific. |
| Comparison | **Discoverable with exploration** | Pin/Compare visible, but scope and intended use are unclear. |
| Notes | **Discoverable with exploration** | Result-panel-local and not part of ordinary research workflow language. |
| Presets/custom weights | **Discoverable with exploration** | Toolbar/Settings expose them, but methodological consequences are subtle. |
| Speech analysis | **Discoverable with exploration** | Nested under Automated coding > Language. |
| Whisper transcription | **Requires documentation** | Split between Settings, Analyze action, captions, and optional tooling. |
| Vocabulary analysis | **Discoverable with exploration** | Direct Language > Vocabulary controls are good once the user reaches that tab. |
| Exports | **Discoverable with exploration** | File menu and local vocabulary export, but disabled/contextual state hides overall data-export workflow. |
| Manual coding/validation | **Requires documentation** | Top-level Human coding exists and guides/codebooks help; relationship to automated results and research protocol remains specialized. |

## Top ten usability problems

1. **No explicit first-run workflow choice — High.** Researchers must translate their research design into tabs/buttons. **Fix:** Pipeline-first chooser for few episodes, reproducible sample, full corpus, subtitles, and validation.
2. **Pipeline-first intent conflicts with checked-in no-library behavior — High.** The intended conceptual entry can be bypassed. **Fix:** test the release build and make the Pipeline dashboard first for every new project.
3. **Sampling is presented as optional machinery, not the core design decision — High.** Novices may batch-analyze then confuse explored files with a designed sample. **Fix:** census/sample/exploration decision before batch analysis.
4. **`Send Sample to CMAT` obscures whether/how analysis begins — High.** This is a likely hard stop immediately after successful sampling. **Fix:** explicit queue handoff and `Start analysis` CTA with counts.
5. **There is no clear cohort-level research dataset/export — High.** Users can export the wrong scope or manually merge files. **Fix:** named study/cohort export with review, data dictionary, and provenance bundle.
6. **Folder naming is a hidden research data model — High.** Historical and lab datasets will not naturally fit it. **Fix:** library import review and registry-first option with stable IDs.
7. **Composite-score interpretation is too easy to overread — High.** A score can be mistaken for child appropriateness, especially with age presets. **Fix:** persistent stimulus-profile disclaimer and transparent score decomposition; rename/reframe presets.
8. **Metadata is not a first-class pre-analysis stage — High.** Longitudinal, sampling, and comparison workflows depend on it. **Fix:** Metadata completeness stage with matching review/provenance/reversibility.
9. **Language workflow prerequisites and blanks are fragmented — High.** Linguists may see missing metrics without actionable explanation. **Fix:** language start route, readiness checker, and per-metric status/reason.
10. **Project/cache/protocol state is invisible to teams — High.** Mixed settings and shared-corpus ambiguity threaten defensibility. **Fix:** project manifest, corpus health dashboard, immutable protocols, and run manifests.

## Top ten improvements by impact × frequency × leverage

1. **Replace default graph-editor onboarding with Start a research workflow.** Routes every new user correctly and leverages existing features.
2. **Create a named Project / Study layer.** Binds library, protocol, samples, metadata, runs, validation, and exports.
3. **Add a “census, sample, or explore?” decision before batch analysis.** Prevents a common research-design error.
4. **Turn sampler handoff into one continuous sample-to-run flow.** Lock manifest, queue, start, progress, and run record in one place.
5. **Build cohort/study export.** One data package, explicit scope and missingness, rather than contextual exports.
6. **Add library import/metadata review.** Decouple research structure from filesystem conventions and make dates available early.
7. **Make the score model visibly inspectable at point of use.** Raw → normalized → weighted → composite, with shared-protocol check.
8. **Add a language-specific first-run route and readiness panel.** Captions, Whisper, NLP packages, norms, supported outputs, export scope.
9. **Create corpus health/protocol lock screens.** Makes cache, stale settings, failures, missing subtitles, and heterogeneous runs auditable.
10. **Create guided comparison/longitudinal workspaces.** Choose cohorts, show coverage/settings/sample constraints, then chart/export.

## Ideal first 15 minutes

1. The application opens to **What are you trying to do?** It says CMAT measures media-stimulus features and language—not child appropriateness—and offers five choices: explore a few videos; create a reproducible episode sample; analyze a complete corpus; study subtitles/language; validate automated measures with human coding.
2. The researcher chooses a path. A short side panel says what files are needed, what will be produced, time/dependency expectations, and a real example.
3. They add a media folder or a registry. CMAT previews detected shows/seasons/episodes and flags ambiguities before treating folders as research units.
4. CMAT asks them to name the project, define corpus/population, and choose/confirm a measurement protocol. It explains that presets are reference ranges, not appropriateness ratings.
5. If sampling, a decision helper proposes a method and records the researcher’s choices/rationale. The researcher previews, names, locks, and immediately starts the selected run; the UI states exactly what will happen next.
6. During analysis, CMAT reports progress and data quality: captions found/missing, Whisper status, failed files, metadata coverage, current protocol/fingerprint.
7. Results open with a plain-language header: **stimulus profile, not a child outcome**, component measures, score derivation, and limitations. The researcher can inspect raw measurements and provenance without hunting in Help.
8. A study dashboard shows: corpus/sample size, analyzed/failed/missing episodes, dates/metadata, protocol consistency, and available next steps: compare, chart, validate, export.
9. Export says exactly what it includes and produces an analysis-ready package with episode data, metadata, sample record, protocols, validation evidence, data dictionary, and provenance.

## Strongest parts of the current UX

- The underlying research intent is unusually explicit: sampling, automation, human coding, validation, and provenance are all present rather than treated as afterthoughts.
- The sampler is carefully structured with numbered steps, dry-run preview, seed, stratification/allocation choices, tooltips, and persistent manifest/CSV/worklist outputs.
- The result model exposes component metrics rather than only a black-box composite.
- The metrics help text responsibly distinguishes stimulus measurement from child-level appropriateness and identifies correlational limitations.
- Measurement fingerprints and stale-cache warnings show excellent awareness that raw-method settings affect comparability.
- The app differentiates automatic and hand-coded status in the Library tree, reducing accidental conflation.
- Metadata import offers matching previews rather than blind writes, and the chart model supports air date/season/era.
- Vocabulary analysis has a direct caption-file route rather than forcing video analysis.
- Human coding, validation, agreement, error annotation, parameter sweep, and Trials form a compelling validation workbench.
- CSV provenance sidecars and sample manifests demonstrate genuine reproducibility values.

## Final product review

CMAT is much stronger as a research system than a superficial first glance would suggest. The principal product problem is not absence of capability; it is the absence of an unmistakable “research study” spine that joins the capabilities. A first-time researcher can discover pieces—folders, sampling, analysis, captions, metadata, validation, export—but should not have to reconstruct their relationship or protect themselves from scope/protocol mistakes by reading the README.

The most valuable product shift is: **from a feature-rich analyzer organized around folders and tabs to a study-oriented toolkit organized around research decisions, locked cohorts, transparent measures, and analysis-ready datasets.**
