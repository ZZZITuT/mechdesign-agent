# Third-party software

MechDesign Agent itself is released under the [MIT License](LICENSE). It uses the
following third-party components. None of them is vendored into this repository.

| Component | How it is used | License |
|---|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | web framework (runtime dependency) | MIT |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server (runtime dependency) | BSD-3-Clause |
| [Pydantic](https://docs.pydantic.dev/) | request and proposal schemas (runtime dependency) | MIT |
| [NumPy](https://numpy.org/) | vectorised design-space search, FE assembly (runtime dependency) | BSD-3-Clause |
| [SciPy](https://scipy.org/) | sparse solver for the continuum FE cross-check (runtime dependency) | BSD-3-Clause |
| [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) | optional LLM interpretation, `[llm]` extra | Apache-2.0 |
| [anaStruct](https://github.com/ritchie46/anaStruct) | optional independent FE cross-check, `[validation]` extra | **GPL-3.0-or-later** |
| [Three.js](https://threejs.org/) 0.160.0 | 3D view, loaded by the browser from the jsDelivr CDN at runtime | MIT |

## Note on anaStruct (GPL)

anaStruct is an **optional** dependency. It is imported only inside
`mechdesign.fem.beam_fe_anastruct`, and only when installed. Without it, the
cross-check reports that the anaStruct comparison was skipped. Nothing else changes.
MechDesign Agent does not include or redistribute anaStruct code.

If you distribute a bundle that includes anaStruct (for example a Docker image
built with the `[validation]` extra), that bundle must comply with the GPL. The
provided `Dockerfile` installs only the `[llm]` extra for this reason.
