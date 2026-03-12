# Wave 2 Runtime Compat

- Epic: centralize execution mechanics behind `PipelineRunner`
- Packages: `miniautogen/core/runtime`, `miniautogen/compat`, `miniautogen/chat`
- Done when:
  - `PipelineRunner` exists and executes current pipelines
  - legacy `ChatPipelineState` can be bridged explicitly
  - `ChatAdmin` delegates to the runner without breaking public behavior
  - controlled AnyIO usage stays internal
  - regression and runtime tests remain green
