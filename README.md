# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                       |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                  |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/annotations/external.py                          |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                           |        9 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                         |       20 |        1 |     95% |        42 |
| src/flync/core/base\_models/\_\_init\_\_.py                     |        2 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                      |       17 |        1 |     94% |        19 |
| src/flync/core/datatypes/\_\_init\_\_.py                        |        8 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitrange.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                          |       44 |        1 |     98% |       122 |
| src/flync/core/datatypes/ipaddress.py                           |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                          |       25 |        0 |    100% |           |
| src/flync/core/datatypes/value\_range.py                        |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                        |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                            |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                             |      118 |       16 |     86% |31, 33, 36, 42-43, 57-65, 83, 224, 264 |
| src/flync/core/utils/common\_validators.py                      |      280 |       39 |     86% |60, 118, 208, 239-242, 322-324, 352, 361, 402, 427, 429, 442, 472, 483, 520, 526, 532, 557, 579, 586, 624-625, 658, 665, 712, 745, 754, 760, 794, 800, 809, 815, 829, 835, 957 |
| src/flync/core/utils/exceptions.py                              |       62 |        0 |    100% |           |
| src/flync/core/utils/exceptions\_handling.py                    |      227 |       18 |     92% |43, 73, 100, 108, 157-161, 165, 178, 182, 198, 225, 249, 251, 589-591 |
| src/flync/core/utils/forwarder\_validators.py                   |      310 |        7 |     98% |55, 268, 293, 315, 619, 669, 691 |
| src/flync/core/utils/interface\_validators.py                   |       71 |        2 |     97% |   45, 153 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py   |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py              |       62 |        3 |     95% |63, 68, 78 |
| src/flync/core/utils/state\_management\_validators.py           |      222 |        4 |     98% |296, 439, 548, 612 |
| src/flync/core/validators/\_\_init\_\_.py                       |        2 |        0 |    100% |           |
| src/flync/core/validators/address\_validators.py                |       10 |        0 |    100% |           |
| src/flync/core/version\_migrators/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py  |       17 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                 |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                   |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                  |       20 |        2 |     90% |    36, 44 |
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
| src/flync/model/flync\_4\_ecu/ecu.py                            |      250 |        9 |     96% |175, 261, 284, 326, 440, 448, 475, 535-536 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py             |      188 |       14 |     93% |50, 131-132, 146, 215-216, 232, 410-411, 421-423, 474-475 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                 |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py       |       27 |        1 |     96% |        91 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py              |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                            |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                           |       29 |        1 |     97% |        86 |
| src/flync/model/flync\_4\_ecu/router.py                         |       15 |        1 |     93% |        69 |
| src/flync/model/flync\_4\_ecu/socket\_container.py              |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                        |       97 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                         |      257 |        5 |     98% |128, 166, 738, 772-773 |
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
| src/flync/model/flync\_4\_signal/pdu.py                         |      106 |        2 |     98% |  361, 364 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py             |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                      |      160 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py             |       94 |        1 |     99% |       125 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                  |       79 |        1 |     99% |       177 |
| src/flync/model/flync\_4\_someip/service\_interface.py          |      219 |        3 |     99% |386, 575, 838 |
| src/flync/model/flync\_4\_someip/someip\_datatypes.py           |      187 |        4 |     98% |500, 511-513 |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/bus\_topology.py             |       94 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/ethernet\_topology.py        |       70 |        6 |     91% |61, 65, 104, 110, 128, 146 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                            |      227 |       18 |     92% |346-351, 360, 369, 375, 479, 483, 493, 606, 658, 698, 738, 775, 814, 853 |
| src/flync/model/flync\_4\_tsn/timesync.py                       |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                 |      344 |       21 |     94% |228, 236, 250-265, 282-283, 307-308, 332-333, 381, 410, 527, 547, 553, 567 |
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
| src/flync/sdk/helpers/generation\_helpers.py                    |      378 |       31 |     92% |59, 64, 86, 144, 234, 276, 306, 339-340, 349-353, 369, 371-372, 397, 421, 484-486, 563, 572, 676, 693, 719, 767, 780-781, 789 |
| src/flync/sdk/helpers/nodes\_helpers.py                         |       17 |        1 |     94% |        55 |
| src/flync/sdk/helpers/validation\_helpers.py                    |       48 |       12 |     75% |81, 129-149 |
| src/flync/sdk/utils/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                             |       16 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                      |      263 |       19 |     93% |71, 95-97, 155, 230, 379, 428, 452, 542-546, 568, 619, 635-636, 654 |
| src/flync/sdk/utils/model\_dumper.py                            |       32 |        4 |     88% | 35, 54-56 |
| src/flync/sdk/utils/sdk\_types.py                               |        4 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/document.py                             |       60 |        3 |     95% |   161-163 |
| src/flync/sdk/workspace/flync\_workspace.py                     |      765 |       81 |     89% |226, 310, 375, 396, 470, 475, 483, 530-535, 689, 722-738, 756, 802, 970, 1009, 1041, 1070, 1129-1130, 1138-1143, 1203, 1210, 1247-1248, 1251-1253, 1271-1273, 1284, 1387, 1391, 1403, 1406-1408, 1520, 1567, 1582, 1621-1636, 1798-1799, 2095, 2192-2201 |
| src/flync/sdk/workspace/ids.py                                  |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                              |       95 |        3 |     97% |   166-169 |
| src/flync/sdk/workspace/source.py                               |       11 |        0 |    100% |           |
| **TOTAL**                                                       | **7498** |  **443** | **94%** |           |


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