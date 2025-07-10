# Changelog

## [0.5.5](https://github.com/runpod/tetra-rp/compare/0.5.4...0.5.5) (2025-07-10)


### Bug Fixes

* remove sigstore signing to simplify PyPI publishing ([65037c5](https://github.com/runpod/tetra-rp/commit/65037c5f4c11bb8a08292b98f17d1f005784e5ed))

## [0.5.4](https://github.com/runpod/tetra-rp/compare/0.5.3...0.5.4) (2025-07-10)


### Bug Fixes

* revert to simple working CI/release workflows, remove broken shared workflow ([3fe4cf0](https://github.com/runpod/tetra-rp/commit/3fe4cf02472e6cc19cd46a8104b248e2e7367be3))
* separate sigstore artifacts from dist/ to avoid PyPI validation errors ([6b0038e](https://github.com/runpod/tetra-rp/commit/6b0038ea1c1df058263d2395248fb96d4c88cdeb))


### Documentation

* add contributing section to README with release system documentation reference ([8b87b9c](https://github.com/runpod/tetra-rp/commit/8b87b9cb09262f5be74a8f18435d685b0360d1c5))

## [0.5.3](https://github.com/runpod/tetra-rp/compare/0.5.2...0.5.3) (2025-07-10)


### Bug Fixes

* update sigstore action to v3.0.0 to avoid deprecated upload-artifact@v3 ([92a6891](https://github.com/runpod/tetra-rp/commit/92a6891e26d327b2c99926373822e0eede08eebb))

## [0.5.2](https://github.com/runpod/tetra-rp/compare/0.5.1...0.5.2) (2025-07-10)


### Bug Fixes

* revert to simple working CI/release workflows, remove broken shared workflow ([62dab19](https://github.com/runpod/tetra-rp/commit/62dab1937be0d6c918261299e3be197cda0f44a9))

## [0.5.1](https://github.com/runpod/tetra-rp/compare/0.5.0...0.5.1) (2025-07-10)


### Bug Fixes

* adjust release-please title pattern to match existing PR [#55](https://github.com/runpod/tetra-rp/issues/55) ([091dbff](https://github.com/runpod/tetra-rp/commit/091dbffe8b26142eeedc07e1855d132e948cc3cd))
* only upload artifacts to release when tag_name is available ([e8bdcf1](https://github.com/runpod/tetra-rp/commit/e8bdcf12cf7aeb57c04232aea2f14174c743481b))
* revert to clean release-please title pattern for future releases ([c0171ca](https://github.com/runpod/tetra-rp/commit/c0171cab08f0ea62a861c1a0b8012e1c4dbd89c7))
* still seeing issues with the CI and Release ([#60](https://github.com/runpod/tetra-rp/issues/60)) ([81df31a](https://github.com/runpod/tetra-rp/commit/81df31a0853c6436964afeb2511499396c66fe0d))

## [0.5.0](https://github.com/runpod/tetra-rp/compare/v0.4.2...0.5.0) (2025-07-09)


### Features

* pytest with unit and integration ([19dcac9](https://github.com/runpod/tetra-rp/commit/19dcac908ddd5f2cdac7d9365c3b2066fbe04fdd))


### Bug Fixes

* cannot do both ([c64d895](https://github.com/runpod/tetra-rp/commit/c64d89550f871b5fb685adc6dcb913cbd61217e4))
* configure release-please to handle all commit types ([#57](https://github.com/runpod/tetra-rp/issues/57)) ([7de5c8d](https://github.com/runpod/tetra-rp/commit/7de5c8d146eaf2fddde07bc9c5ecf260e37029e3))
* correction ([9982236](https://github.com/runpod/tetra-rp/commit/99822362fd99698a30ddcaab6bbd5513ed5549d8))
* Pydantic's deprecation warning of class Config ([d1f18f2](https://github.com/runpod/tetra-rp/commit/d1f18f207568866aadb487ca99747b542174142b))
* ruff cleanup ([8251597](https://github.com/runpod/tetra-rp/commit/825159748fdb8755aeee03d1740081915fd0882f))
* ruff linting ([6d8e87c](https://github.com/runpod/tetra-rp/commit/6d8e87cb095b8d38977c5b3bfe981c8ebe580c93))


### Documentation

* pull request template ([#58](https://github.com/runpod/tetra-rp/issues/58)) ([0377fa4](https://github.com/runpod/tetra-rp/commit/0377fa4dfc439e56df30227a03cf77bb80dfa28a))

## [0.4.2](https://github.com/runpod/tetra-rp/compare/v0.4.1...v0.4.2) (2025-06-26)


### Bug Fixes

* consolidate PodTemplate overrides with the defaults per ServerlessResource ([2b8dc16](https://github.com/runpod/tetra-rp/commit/2b8dc165c46ce5d70651f7060075815977034557))
* template overrides ([0fd6429](https://github.com/runpod/tetra-rp/commit/0fd6429ee1ad5ade9df5bfc4bbbdc9f29683b75b))

## [0.4.1](https://github.com/runpod/tetra-rp/compare/v0.4.0...v0.4.1) (2025-06-26)


### Bug Fixes

* uv publish ([6c4f9a9](https://github.com/runpod/tetra-rp/commit/6c4f9a9d4deeffc4733798208e771cd136ab2e80))
* uv publish ([55ae7c0](https://github.com/runpod/tetra-rp/commit/55ae7c08d70e079bb0abe2938b0d13771de3dce1))

## [0.4.0](https://github.com/runpod/tetra-rp/compare/v0.3.0...v0.4.0) (2025-06-26)


### Features

* CPU Endpoints and Live Serverless ([c335fd1](https://github.com/runpod/tetra-rp/commit/c335fd11cbc65c4a18edabe007982506bee5e6c3))


### Bug Fixes

* CpuInstanceType values ([9cf958b](https://github.com/runpod/tetra-rp/commit/9cf958b381d56b4aa5d42c0393500818d6de3c34))

## [0.3.0](https://github.com/runpod/tetra-rp/compare/v0.2.1...v0.3.0) (2025-06-23)


### Features

* added diffusers as examples group dependency ([e330bf9](https://github.com/runpod/tetra-rp/commit/e330bf9ed2305470543dd39470c1803959479821))
* AE-392: serverless execute function calls runpod SDK ([43900e5](https://github.com/runpod/tetra-rp/commit/43900e59e3c4e08b5a903751ce5525fcfee93f13))
* AE-394: examples updated ([27c3afb](https://github.com/runpod/tetra-rp/commit/27c3afbb93667d7a800af0f3e49361cb5b806070))
* AE-394: examples updated ([d2bfe1b](https://github.com/runpod/tetra-rp/commit/d2bfe1b8c8682655a62148fcc3d0f0041a2f35d4))
* AE-394: LiveServerless that locks the template id ([d1032a6](https://github.com/runpod/tetra-rp/commit/d1032a6b2788a18eb19eee991134fb8152733a11))
* AE-394: LiveServerless that locks the template id ([1ba5bfc](https://github.com/runpod/tetra-rp/commit/1ba5bfce5d597a040ad66358dad2a86b0a66c3d6))
* AE-394: resilient serverless calls with retries and auto-cancellations ([78bb250](https://github.com/runpod/tetra-rp/commit/78bb2505b7f7e02c82a2fe54ca1643de73affb54))
* AE-394: retry, backoff, on cancel appropriately ([4b75941](https://github.com/runpod/tetra-rp/commit/4b759419f322f1dac87b4fd65d19430928ff9144))
* AE-394: retry, backoff, on cancel appropriately ([96d1001](https://github.com/runpod/tetra-rp/commit/96d1001915654d3f101ac32bde972f17a0a3ff22))
* AE-432: Logging ([a93f88e](https://github.com/runpod/tetra-rp/commit/a93f88e20a2fb0f6d741aebe98db85cc8b3ed88b))
* AE-432: Logging ([718de18](https://github.com/runpod/tetra-rp/commit/718de18289b2d605ecc01359c6be9b6290373d3a))
* AE-442: Docker image template polish + cleanup ([75471b2](https://github.com/runpod/tetra-rp/commit/75471b2cbb40d31d0d82d4562072d8c16a59cb8e))
* AE-470: shadow deploy as tetra_rp ([749d427](https://github.com/runpod/tetra-rp/commit/749d427b9095d77742ddde679d1fc44d999d5d30))
* AE-494: remove all docker- worker-related content ([72a4b9a](https://github.com/runpod/tetra-rp/commit/72a4b9a74761affdb1b0e9381bcaf49763829bac))
* AE-494: removed any worker-related content ([72464d1](https://github.com/runpod/tetra-rp/commit/72464d1881584a2003d2edbd2cf9e6a982455592))
* AE-517: logs from remote printed as `Remote | <log>` ([d8f4ee1](https://github.com/runpod/tetra-rp/commit/d8f4ee1323696b3f9cd8e5c2e928eb8538c6d2cd))
* AE-517: logs from remote printed as `Remote | <log>` ([ab1d729](https://github.com/runpod/tetra-rp/commit/ab1d72900e21cccebd5448f63220295f113aeeb1))
* AE-517: remote error logs are piped back ([b668e3e](https://github.com/runpod/tetra-rp/commit/b668e3ef0d97babebfaf35f31d053be8fbee7ad9))
* AE-517: remote error logs are piped back ([4c5bf4c](https://github.com/runpod/tetra-rp/commit/4c5bf4c03d85a55a10739ea0911cff7d257ffe1b))
* AE-565 singledispatch stub_resource for LiveServerless ([5fe2de7](https://github.com/runpod/tetra-rp/commit/5fe2de7cf74fc39ced6699aeb6cf4f48af21f3e9))
* incremental changes, starting with deployments ([1ce1b3b](https://github.com/runpod/tetra-rp/commit/1ce1b3b04c2fdff2bfb870c6b9065bd6213a506d))
* is_deployed() to check and redeploy in case endpoint is inaccessible ([4aa0932](https://github.com/runpod/tetra-rp/commit/4aa0932c9f99b08a0d234d4d843dd6339cbc7dd1))
* Prefer A40 for GPU list when "any" is set ([6a60418](https://github.com/runpod/tetra-rp/commit/6a60418452a39501b3142096e9ab8afa01628953))
* preparing json.dump of complex objects with normalize_for_json ([48cedd6](https://github.com/runpod/tetra-rp/commit/48cedd64e9140d261f2b3327a3611715d2bf3e38))
* Pydantic modeling of Runpod resources ([87067bb](https://github.com/runpod/tetra-rp/commit/87067bbae31d7de618d0edd1d78289fef1c0f6d1))
* remote stub for ServerlessEndpoint calls ([739aa93](https://github.com/runpod/tetra-rp/commit/739aa93775e296fbb99aa9afccc07b12ae60ea50))
* resilient redeployments ([fd2e78d](https://github.com/runpod/tetra-rp/commit/fd2e78d42531f83cc3b66d197fb2195244d65336))
* resilient serverless calls with retries and auto-cancellations when unhealthy/throttled ([9f53e8c](https://github.com/runpod/tetra-rp/commit/9f53e8cb36871ff58b491cd8bf1851bf3d1029cc))
* resource utility, `inquire` to map runpod calls to pydantic models ([096239f](https://github.com/runpod/tetra-rp/commit/096239fae42dbcfafb141b48f294942e0e840990))
* ServerlessEndpoint inherits ServerlessResource ([c0e64f9](https://github.com/runpod/tetra-rp/commit/c0e64f930bf38f2a956463d74f6bccfafee13353))
* ServerlessResource.run_sync ([33e3fff](https://github.com/runpod/tetra-rp/commit/33e3fffeb121977c14614f0f0d57cfb232756e8c))
* SingletonMixin for ResourceManager and RemoteExecutionClient ([e0ae91b](https://github.com/runpod/tetra-rp/commit/e0ae91b0627226873b131abdb26ab6d86e88e4d2))
* Support for ServerlessEndpoint remote calls ([e53f3aa](https://github.com/runpod/tetra-rp/commit/e53f3aa4ef44f6e8a87d2d37fe7ae9b5f10e29f6))


### Bug Fixes

* add missing arg to request ([21d4e0c](https://github.com/runpod/tetra-rp/commit/21d4e0ceb6e255a5d5df1440c8fcbe95a75f802c))
* add missing arg to request ([656150f](https://github.com/runpod/tetra-rp/commit/656150fc082b7b519d4b6c940258af8ac0b62e04))
* AE-392: deployable serverless corrections ([57b1cd2](https://github.com/runpod/tetra-rp/commit/57b1cd21fa63bd9d11447cdba9a865ca1a3aeb8b))
* AE-392: deployable serverless corrections ([74bd17d](https://github.com/runpod/tetra-rp/commit/74bd17d0dbf7bd24ddf3de3734405615a12af1a8))
* cleanup from ruff suggestions ([61048d2](https://github.com/runpod/tetra-rp/commit/61048d2d7922ad53289fa078f9e48ac8b60dada7))
* cleanup project setup ([9ed50ab](https://github.com/runpod/tetra-rp/commit/9ed50ab925e465ffeb8cedbffbb44036bdfb35c8))
* cleanup unused code ([ad78de7](https://github.com/runpod/tetra-rp/commit/ad78de7942587dbb0100a3101a5185ebc1c0cc52))
* implicit load_dotenv() before everything ([ff0030b](https://github.com/runpod/tetra-rp/commit/ff0030bd7c033d4a8e6b9849c76075bccb99beaa))
* implicit load_dotenv() before everything ([2d3c710](https://github.com/runpod/tetra-rp/commit/2d3c71015a944515fa667aaa662692f14596b5e0))
* make examples ([7de342c](https://github.com/runpod/tetra-rp/commit/7de342cafab59bffe764833d5a1f02b7ff691654))
* missed these commits ([5ed3a8a](https://github.com/runpod/tetra-rp/commit/5ed3a8a4bc6065eb1c4313595f325581666d33ae))
* passing GPU names aren't supported yet ([3798ac0](https://github.com/runpod/tetra-rp/commit/3798ac06ce1de21b711f5a7236ebaa884ffc22ae))
* Put A40s in front of the list when gpus=any ([717efb1](https://github.com/runpod/tetra-rp/commit/717efb168059826ce2857c3be3d476a43e0eddfb))
* python 3.9 compatible ([5ddfd09](https://github.com/runpod/tetra-rp/commit/5ddfd09d2fba9403aec9940eec479db5f259c1d8))
* release-please bugs ([fd6d02e](https://github.com/runpod/tetra-rp/commit/fd6d02eb2a625082e2f31394577debc5c066b0f4))
* release-please bugs ([76b3eee](https://github.com/runpod/tetra-rp/commit/76b3eee81d5a7e9a4eca1b06b0cdc6256d4d9743))
* ruff cleanup ([739adaf](https://github.com/runpod/tetra-rp/commit/739adaff98f816dfb95f6b46887ba80b6e8e2aaa))
* simplify `make dev` that syncs and installs examples ([d1a3e62](https://github.com/runpod/tetra-rp/commit/d1a3e62174b066330591a96cc98d7b7e1238f221))
* try catch for matrix example ([f7a5012](https://github.com/runpod/tetra-rp/commit/f7a5012a1f177e96e3565ec86638e2712846bb71))
* use of pathlib.Path where appropriate ([4ee717c](https://github.com/runpod/tetra-rp/commit/4ee717ca853ce88598c60db0cc3770b1f689d0ce))

## [0.2.1](https://github.com/runpod/tetra-rp/compare/0.2.0...v0.2.1) (2025-06-23)


### Bug Fixes

* implicit load_dotenv() before everything ([2d3c710](https://github.com/runpod/tetra-rp/commit/2d3c71015a944515fa667aaa662692f14596b5e0))
