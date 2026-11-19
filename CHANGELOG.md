# Changelog

## 2.0.0 (2026-11-19)


### ⚠ BREAKING CHANGES

* remove the v1 code and its baseline tests
* move v1 code to legacy/ ahead of the 2.0 rewrite

### Features

* add a geocode cache setting and GeocodingError ([0409e3e](https://github.com/guerrad49/gyms/commit/0409e3e881e0bbad79f64e888a7488cfa41bc0c7))
* add a row handle to Gym and store error types ([f0daab2](https://github.com/guerrad49/gyms/commit/f0daab21770a046755028d8424515a4d319be086))
* add address lookup with rate limiting, retries and a cache ([a66c810](https://github.com/guerrad49/gyms/commit/a66c810c9964d2c8a81d48157499adb83ea09db6))
* add CSV, SQLite and Google Sheets storage behind one interface ([4122500](https://github.com/guerrad49/gyms/commit/41225000c8f3da9060a7d8ade76bdafc32ab3540))
* add device profiles with detection and scaling ([46f8a10](https://github.com/guerrad49/gyms/commit/46f8a1080535c4851286272625bce8b60d801667))
* add domain models, error types and text parsers ([690a221](https://github.com/guerrad49/gyms/commit/690a221879181ce210dcac704f6b483415462da1))
* add image loading and OCR preprocessing ([056072a](https://github.com/guerrad49/gyms/commit/056072a9d6ee5501987135d4b077923048be6be8))
* add near-miss and raw-text diagnostics to pogo eval ([cda2ced](https://github.com/guerrad49/gyms/commit/cda2cedf5f542c52ce1188480f2e23406b777036))
* add OCR engine interface and Tesseract engine ([e1095f9](https://github.com/guerrad49/gyms/commit/e1095f9a10603eed0ca3ad90eab18a567101257e))
* add pogo eval to benchmark OCR against database ([6fd241c](https://github.com/guerrad49/gyms/commit/6fd241ca1e1864511eb82c3fd35a8010b39f35ed))
* add pogo resolve ([55b6e58](https://github.com/guerrad49/gyms/commit/55b6e5852385239041eca7a0d1e62165d6d06683))
* add pogo scan and pogo doctor ([735ed69](https://github.com/guerrad49/gyms/commit/735ed699fbbbc08ceed3a047964ce79cc85fc1f3))
* add pogo upgrade, migrate and export commands ([7df3fc4](https://github.com/guerrad49/gyms/commit/7df3fc4c650a2c13923fd9b629e69ffc06f0a539))
* add scheme upgrade, migration and My Maps export ([24559e8](https://github.com/guerrad49/gyms/commit/24559e855ce27050d97714d03f21ff054e72da53))
* add the environment checks behind pogo doctor ([ee77aaa](https://github.com/guerrad49/gyms/commit/ee77aaabfeb6387b385ccb878ba53ee8a8632fc6))
* add the scan pipeline ([a5e2d1a](https://github.com/guerrad49/gyms/commit/a5e2d1ac053a266f27cb20526fc6d8322cc0bdfe))
* add title matching and nearby duplicate detection ([68df48f](https://github.com/guerrad49/gyms/commit/68df48f5c9ef8300444acd17a24adb6a8e5fe58c))
* load settings from file, environment and options ([c97771a](https://github.com/guerrad49/gyms/commit/c97771a1c6b0629a5ebfb4164c6f74abd9d6ea15))
* read badges using ranked title variants ([499d4cb](https://github.com/guerrad49/gyms/commit/499d4cb47091c3c1f7ef617e9319a2f3d4842c36))
* retry Google Sheets quota errors and wrap API failures ([381edec](https://github.com/guerrad49/gyms/commit/381edece56521fbcbfce1d78c2cb938847d00c6f))
* show expected and read statistics and discarded words in pogo eval ([ebed466](https://github.com/guerrad49/gyms/commit/ebed466981f3d2c02818aa4990b5521a0163e2c6))


### Bug Fixes

* adapt the real gspread worksheet to the store interface ([d086037](https://github.com/guerrad49/gyms/commit/d086037596004adb006bd02c00afd471feef7a19))
* keep ampersands and dashes when reading titles ([1f78456](https://github.com/guerrad49/gyms/commit/1f78456f4bb81ffcf04bfd58b0b273cad5e9f3c3))
* prefer a clean title reading over one with status-bar text ([cfb12a5](https://github.com/guerrad49/gyms/commit/cfb12a592b2b372ff20d713f2fd5a0d41dca2d73))
* read a bar between title words as a capital i ([d708b22](https://github.com/guerrad49/gyms/commit/d708b222cd11d181fc0721a324bc0ed5124240cc))
* read look-alike letters as digits inside time values ([63bf648](https://github.com/guerrad49/gyms/commit/63bf648c61f9e695199240ddff35913c456d7bcc))
* say when a prompt got no answer instead of claiming a skip ([1234514](https://github.com/guerrad49/gyms/commit/1234514445818932f054f87bdd2a993349388cfb))
* store coordinate as floats and add Gym.remove_flag ([12ef7c7](https://github.com/guerrad49/gyms/commit/12ef7c73a0b90c1390f68dc2a0d4ada71470635d))
* treat 1 and i as the same letter when comparing titles ([6c91132](https://github.com/guerrad49/gyms/commit/6c911327b43902dc2a5b4fc2bcb3631ec8b150d4))


### Code Refactoring

* move v1 code to legacy/ ahead of the 2.0 rewrite ([9ff5d68](https://github.com/guerrad49/gyms/commit/9ff5d68650807da809c61dc07e64b654ec7949ee))
* remove the v1 code and its baseline tests ([9f6640c](https://github.com/guerrad49/gyms/commit/9f6640c6ce4576ae44c8e96fec8acc1fb2f4ec4f))

## Changelog

All notable changes to this project are recorded here. This file is
generated from the commit messages by the release workflow; see
CONTRIBUTING.md.
