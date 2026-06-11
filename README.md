# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                                |    Stmts |     Miss |   Cover |   Missing |
|-------------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                           |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                      |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                          |        3 |        0 |    100% |           |
| src/flync/core/annotations/external.py                              |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                               |        9 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                             |        8 |        0 |    100% |           |
| src/flync/core/base\_models/\_\_init\_\_.py                         |        6 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                          |       22 |        1 |     95% |        21 |
| src/flync/core/base\_models/dict\_instances.py                      |       34 |        1 |     97% |        83 |
| src/flync/core/base\_models/instances\_registery.py                 |       48 |       10 |     79% |41, 80, 93-97, 132, 150-151 |
| src/flync/core/base\_models/list\_instances.py                      |       27 |        6 |     78% |     78-83 |
| src/flync/core/base\_models/unique\_name.py                         |       22 |        1 |     95% |        23 |
| src/flync/core/datatypes/\_\_init\_\_.py                            |        7 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                    |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitrange.py                                |        5 |        0 |    100% |           |
| src/flync/core/datatypes/ipaddress.py                               |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                              |       25 |        0 |    100% |           |
| src/flync/core/datatypes/value\_range.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                            |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                                |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                                 |      118 |       16 |     86% |31, 33, 36, 42-43, 57-65, 83, 224, 264 |
| src/flync/core/utils/common\_validators.py                          |      246 |       37 |     85% |55, 113, 163, 211-214, 294-296, 324, 331, 370, 395, 397, 406, 438, 448, 450, 452, 473, 491, 498, 528, 531, 534, 563, 571, 602, 611, 613, 643, 649, 658, 664, 674, 680 |
| src/flync/core/utils/exceptions.py                                  |       14 |        0 |    100% |           |
| src/flync/core/utils/exceptions\_handling.py                        |      223 |       18 |     92% |43, 73, 95-96, 117, 126, 128, 188, 278-281, 479-482, 547-549 |
| src/flync/core/utils/forwarder\_validators.py                       |      270 |       11 |     96% |54, 203, 205, 224, 262, 377, 406, 498, 501, 548, 570 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py       |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py                  |       60 |        2 |     97% |    53, 58 |
| src/flync/core/validators/\_\_init\_\_.py                           |        2 |        0 |    100% |           |
| src/flync/core/validators/address\_validators.py                    |       10 |        0 |    100% |           |
| src/flync/core/version\_migrators/\_\_init\_\_.py                   |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py      |       21 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                     |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                           |       51 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/lin\_bus.py                           |       39 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                       |       13 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                     |       25 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller.py                         |      233 |        8 |     97% |361, 427, 431, 445, 450, 452, 464, 684 |
| src/flync/model/flync\_4\_ecu/ecu.py                                |      189 |       17 |     91% |149, 175, 204, 306, 310, 314, 318, 327-333, 341, 374-377 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py                 |      184 |       25 |     86% |50, 127-128, 140-143, 201-202, 214-217, 374-375, 379-380, 385-387, 390-392, 440-441 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                     |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py           |       27 |        1 |     96% |        89 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py                  |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                                |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                               |       29 |        1 |     97% |        86 |
| src/flync/model/flync\_4\_ecu/router.py                             |       15 |        1 |     93% |        69 |
| src/flync/model/flync\_4\_ecu/socket\_container.py                  |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                            |      105 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                             |      182 |        3 |     98% |126, 164, 529 |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                        |       26 |        1 |     96% |        56 |
| src/flync/model/flync\_4\_general\_configuration/\_\_init\_\_.py    |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_general\_configuration/flync\_channels.py |       46 |        1 |     98% |       145 |
| src/flync/model/flync\_4\_general\_configuration/flync\_general.py  |       12 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py                  |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                      |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                             |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                      |       38 |        4 |     89% |38, 42, 44, 46 |
| src/flync/model/flync\_4\_security/macsec.py                        |       42 |        2 |     95% |  134, 140 |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                    |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                       |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                           |       74 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                             |      106 |        2 |     98% |  362, 365 |
| src/flync/model/flync\_4\_signal/signal.py                          |      166 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py                 |      107 |        1 |     99% |       179 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                    |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                      |       97 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/service\_interface.py              |      235 |       10 |     96% |417-420, 440, 883-884, 894-895, 898 |
| src/flync/model/flync\_4\_someip/someip\_datatypes.py               |      188 |        8 |     96% |500, 507-509, 581, 587, 590, 595 |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py                  |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/system\_topology.py              |       57 |        6 |     89% |105, 112, 120, 129, 138, 147 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                                |      226 |       18 |     92% |331-336, 345, 354, 360, 464, 468, 478, 587, 637, 675, 713, 748, 785, 822 |
| src/flync/model/flync\_4\_tsn/timesync.py                           |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                     |      209 |       30 |     86% |121, 153-154, 174-175, 197-198, 226, 247, 322, 326-329, 340-343, 346, 349, 355, 359-362, 366-369, 373 |
| src/flync/sdk/\_\_init\_\_.py                                       |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                               |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                        |       24 |        2 |     92% |     71-72 |
| src/flync/sdk/context/node\_info.py                                 |        9 |        0 |    100% |           |
| src/flync/sdk/context/workspace\_config.py                          |       21 |        3 |     86% |     69-71 |
| src/flync/sdk/helpers/\_\_init\_\_.py                               |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/generation\_helpers.py                        |      244 |      169 |     31% |44-52, 60, 73-80, 84, 88-103, 107-123, 137, 146-151, 165-173, 189-201, 220-226, 240-246, 255-283, 287-307, 319-322, 334-337, 378-388, 393-397, 418-422, 430-448, 460-480 |
| src/flync/sdk/helpers/nodes\_helpers.py                             |       17 |        5 |     71% | 34, 54-57 |
| src/flync/sdk/helpers/validate\_examples.py                         |       11 |       11 |      0% |      8-29 |
| src/flync/sdk/helpers/validation\_helpers.py                        |       48 |       12 |     75% |81, 129-149 |
| src/flync/sdk/utils/\_\_init\_\_.py                                 |        0 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                                 |       16 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                          |      258 |       13 |     95% |95-97, 405, 444, 528-532, 601, 617, 635 |
| src/flync/sdk/utils/model\_dumper.py                                |       13 |        0 |    100% |           |
| src/flync/sdk/utils/sdk\_types.py                                   |        4 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/document.py                                 |       19 |        2 |     89% |     69-70 |
| src/flync/sdk/workspace/flync\_workspace.py                         |      505 |       69 |     86% |161, 249, 266, 287, 361, 366, 374, 421-426, 469-473, 568, 601-616, 634, 678, 847, 909, 963, 1022-1023, 1028, 1030-1035, 1095, 1102, 1127, 1142, 1181-1196, 1332-1333, 1474, 1552, 1594, 1613-1622 |
| src/flync/sdk/workspace/ids.py                                      |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                                  |        6 |        0 |    100% |           |
| src/flync/sdk/workspace/source.py                                   |        7 |        0 |    100% |           |
| src/flync\_cli/\_\_init\_\_.py                                      |        2 |        0 |    100% |           |
| src/flync\_cli/commands/generate\_system\_uml.py                    |      354 |       36 |     90% |115-132, 179, 203-204, 376, 379, 397, 486-487, 490-493, 496-500, 557, 559, 561, 563, 566-568, 578-579 |
| src/flync\_cli/commands/info.py                                     |      103 |        1 |     99% |        82 |
| src/flync\_cli/commands/service\_info.py                            |       42 |        2 |     95% |     90-91 |
| src/flync\_cli/commands/validate.py                                 |       33 |        6 |     82% |36-37, 47, 54-55, 57 |
| src/flync\_cli/commands/vlan\_info.py                               |       67 |        2 |     97% |    87, 94 |
| src/flync\_cli/convert\_puml.py                                     |       71 |        1 |     99% |       283 |
| src/flync\_cli/main.py                                              |       24 |        5 |     79% | 38-41, 45 |
| src/flync\_cli/utils/error\_table.py                                |       87 |       22 |     75% |108-121, 134-149 |
| src/flync\_cli/utils/mapping.py                                     |        3 |        0 |    100% |           |
| src/flync\_cli/utils/run\_validation.py                             |       14 |        6 |     57% |     17-23 |
| src/flync\_converter/\_\_init\_\_.py                                |       34 |        0 |    100% |           |
| src/flync\_converter/\_\_main\_\_.py                                |        5 |        5 |      0% |       1-7 |
| src/flync\_converter/base/\_\_init\_\_.py                           |        3 |        0 |    100% |           |
| src/flync\_converter/base/base\_converter.py                        |       18 |        3 |     83% |54, 66, 78 |
| src/flync\_converter/base/converter\_config.py                      |        2 |        0 |    100% |           |
| src/flync\_converter/cli/\_\_init\_\_.py                            |       14 |        8 |     43% |20-23, 28-30, 35-37, 41 |
| src/flync\_converter/cli/commands.py                                |       77 |        0 |    100% |           |
| src/flync\_converter/cli/dynamic.py                                 |       39 |        0 |    100% |           |
| src/flync\_converter/cli/group.py                                   |       18 |        0 |    100% |           |
| src/flync\_converter/cli/gui/\_\_init\_\_.py                        |        2 |        0 |    100% |           |
| src/flync\_converter/cli/gui/app.py                                 |      113 |       12 |     89% |126-128, 140, 145, 179-180, 189-193 |
| src/flync\_converter/cli/gui/widgets/\_\_init\_\_.py                |        3 |        0 |    100% |           |
| src/flync\_converter/cli/gui/widgets/converter\_panel.py            |      130 |       10 |     92% |29-30, 111-113, 145, 166, 168-170 |
| src/flync\_converter/cli/gui/widgets/log\_handler.py                |       15 |        2 |     87% |     37-38 |
| src/flync\_converter/cli/interactive.py                             |       59 |        0 |    100% |           |
| src/flync\_converter/cli/tui/\_\_init\_\_.py                        |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/app.py                                 |       91 |       91 |      0% |     3-198 |
| src/flync\_converter/cli/tui/utils.py                               |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/widgets/\_\_init\_\_.py                |        3 |        3 |      0% |       3-6 |
| src/flync\_converter/cli/tui/widgets/converter\_panel.py            |       97 |       97 |      0% |     3-199 |
| src/flync\_converter/cli/tui/widgets/log\_handler.py                |       17 |       17 |      0% |      3-34 |
| src/flync\_converter/cli/types.py                                   |       32 |        0 |    100% |           |
| src/flync\_converter/converters/\_\_init\_\_.py                     |        5 |        0 |    100% |           |
| src/flync\_converter/converters/dbc\_converter.py                   |      115 |        0 |    100% |           |
| src/flync\_converter/converters/flync\_converter.py                 |       28 |        0 |    100% |           |
| src/flync\_converter/converters/helpers.py                          |        4 |        0 |    100% |           |
| src/flync\_converter/converters/json\_converter.py                  |       49 |        4 |     92% |41, 57, 69, 84 |
| src/flync\_converter/converters/yaml\_converter.py                  |       49 |        4 |     92% |42, 58, 70, 85 |
| src/flync\_converter/hookspec.py                                    |        4 |        0 |    100% |           |
| src/flync\_converter/registry.py                                    |       32 |        5 |     84% | 29, 55-58 |
| src/flync\_converter/utils.py                                       |       75 |        4 |     95% |63-64, 93-94 |
| **TOTAL**                                                           | **7419** |  **878** | **88%** |           |


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