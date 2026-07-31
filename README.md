# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                       |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                  |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/annotations/external.py                          |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                           |        9 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                         |       20 |        1 |     95% |        40 |
| src/flync/core/base\_models/\_\_init\_\_.py                     |        2 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                      |       17 |        1 |     94% |        19 |
| src/flync/core/datatypes/\_\_init\_\_.py                        |        8 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitrange.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                          |       44 |        1 |     98% |       120 |
| src/flync/core/datatypes/ipaddress.py                           |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                          |       25 |        0 |    100% |           |
| src/flync/core/datatypes/value\_range.py                        |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                        |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                            |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                             |      118 |       16 |     86% |31, 33, 36, 42-43, 57-65, 83, 224, 264 |
| src/flync/core/utils/common\_validators.py                      |      272 |       38 |     86% |60, 118, 208, 239-242, 322-324, 352, 361, 402, 427, 429, 442, 478, 490, 496, 502, 527, 549, 556, 588, 595, 602, 635, 647, 680, 689, 695, 729, 735, 744, 750, 764, 770, 892 |
| src/flync/core/utils/exceptions.py                              |       62 |        0 |    100% |           |
| src/flync/core/utils/exceptions\_handling.py                    |      223 |       21 |     91% |43, 73, 95-96, 117, 126, 128, 147-151, 155, 168, 172, 188, 241, 243, 245, 547-549 |
| src/flync/core/utils/forwarder\_validators.py                   |      307 |        7 |     98% |55, 253, 278, 300, 604, 654, 676 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py   |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py              |       62 |        3 |     95% |54, 59, 69 |
| src/flync/core/utils/state\_management\_validators.py           |      222 |        4 |     98% |296, 439, 548, 612 |
| src/flync/core/validators/\_\_init\_\_.py                       |        2 |        0 |    100% |           |
| src/flync/core/validators/address\_validators.py                |       10 |        0 |    100% |           |
| src/flync/core/version\_migrators/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py  |       21 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                 |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                   |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                  |       20 |        2 |     90% |    34, 42 |
| src/flync/model/flync\_4\_app/application.py                    |       18 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                       |       48 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/lin\_bus.py                       |       42 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/\_\_init\_\_.py         |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/flync\_channels.py      |       58 |        1 |     98% |       163 |
| src/flync/model/flync\_4\_communication/flync\_communication.py |       14 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                   |       15 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                 |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller.py                     |      250 |        7 |     97% |417, 421, 439, 444, 446, 551, 725 |
| src/flync/model/flync\_4\_ecu/controller\_interface.py          |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/ecu.py                            |      202 |       16 |     92% |167, 195, 226, 338, 346, 350, 359-365, 373, 406-409 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py             |      182 |       19 |     90% |50, 131-132, 146, 215-216, 232, 399-400, 404-405, 410-412, 415-417, 465-466 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                 |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py       |       27 |        1 |     96% |        89 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py              |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                            |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                           |       29 |        1 |     97% |        86 |
| src/flync/model/flync\_4\_ecu/router.py                         |       15 |        1 |     93% |        69 |
| src/flync/model/flync\_4\_ecu/socket\_container.py              |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                        |       97 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                         |      268 |        5 |     98% |128, 166, 727, 761-762 |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                    |       26 |        1 |     96% |        56 |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py              |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                  |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/state\_management.py               |       90 |        2 |     98% |   415-416 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                         |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                  |       38 |        4 |     89% |38, 44, 46, 48 |
| src/flync/model/flync\_4\_security/macsec.py                    |       42 |        2 |     95% |  134, 140 |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                   |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                       |       68 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                         |      106 |        2 |     98% |  352, 355 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py             |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                      |      160 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py             |       94 |        1 |     99% |       125 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                  |       77 |        1 |     99% |       174 |
| src/flync/model/flync\_4\_someip/service\_interface.py          |      221 |        7 |     97% |396, 585, 851-852, 862-863, 866 |
| src/flync/model/flync\_4\_someip/someip\_datatypes.py           |      188 |        8 |     96% |500, 511-513, 589, 595, 598, 607 |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py              |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/system\_topology.py          |       56 |        7 |     88% |60, 64, 99, 105, 114, 123, 141 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                            |      227 |       14 |     94% |347-348, 351, 360, 369, 375, 483, 606, 658, 698, 738, 775, 814, 853 |
| src/flync/model/flync\_4\_tsn/timesync.py                       |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                 |      286 |       14 |     95% |146, 199-200, 224-225, 249-250, 279, 302, 324, 423, 443, 449, 463 |
| src/flync/sdk/\_\_init\_\_.py                                   |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                    |       24 |        2 |     92% |     71-72 |
| src/flync/sdk/context/node\_info.py                             |        9 |        1 |     89% |        41 |
| src/flync/sdk/context/workspace\_config.py                      |       21 |        3 |     86% |     69-71 |
| src/flync/sdk/helpers/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/debug.py                                  |      112 |        9 |     92% |41-42, 74-75, 156, 159, 210, 229-231 |
| src/flync/sdk/helpers/debug\_layers/\_\_init\_\_.py             |        2 |        0 |    100% |           |
| src/flync/sdk/helpers/debug\_layers/layer1\_structure.py        |      129 |        6 |     95% |64-65, 96, 216, 220, 235 |
| src/flync/sdk/helpers/debug\_layers/layer2\_yaml.py             |       42 |        4 |     90% |39-41, 71-72 |
| src/flync/sdk/helpers/debug\_layers/layer3\_4\_5\_workspace.py  |      233 |       58 |     75% |105, 124, 154, 276-277, 413-414, 424, 427, 431, 436, 448-449, 455-463, 475-476, 489, 509, 513, 519-536, 547-557, 562-571 |
| src/flync/sdk/helpers/debug\_layers/runner.py                   |      116 |        8 |     93% |58, 66, 127-129, 164, 189-190 |
| src/flync/sdk/helpers/generation\_helpers.py                    |      258 |       59 |     77% |40-48, 70, 217, 261, 279, 356-358, 419, 425-429, 450-454, 462-480, 492-511 |
| src/flync/sdk/helpers/nodes\_helpers.py                         |       17 |        4 |     76% |     54-57 |
| src/flync/sdk/helpers/validation\_helpers.py                    |       48 |       12 |     75% |81, 129-149 |
| src/flync/sdk/utils/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                             |       16 |        4 |     75% |     66-69 |
| src/flync/sdk/utils/model\_dependencies.py                      |      267 |       18 |     93% |71, 95-97, 155, 197, 231, 407, 433, 457, 547-551, 575, 626, 661 |
| src/flync/sdk/utils/model\_dumper.py                            |       32 |        4 |     88% | 35, 54-56 |
| src/flync/sdk/utils/sdk\_types.py                               |        4 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/document.py                             |       58 |        4 |     93% |143, 163-165 |
| src/flync/sdk/workspace/flync\_workspace.py                     |      554 |       68 |     88% |168, 271, 295, 313, 334, 408, 413, 421, 468-473, 615, 648-663, 681, 725, 894, 930, 956, 1010, 1069-1070, 1078-1083, 1143, 1150, 1175, 1190, 1229-1244, 1312, 1404-1405, 1667, 1689, 1764-1773 |
| src/flync/sdk/workspace/ids.py                                  |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                              |       69 |        0 |    100% |           |
| src/flync/sdk/workspace/source.py                               |       11 |        0 |    100% |           |
| **TOTAL**                                                       | **6852** |  **472** | **93%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/Technica-Engineering/FLYNC/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/Technica-Engineering/FLYNC/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FTechnica-Engineering%2FFLYNC%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.