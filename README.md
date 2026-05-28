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
| src/flync/core/base\_models/instances\_registery.py                 |       42 |        5 |     88% |41, 80, 115, 133-134 |
| src/flync/core/base\_models/list\_instances.py                      |       27 |        6 |     78% |     78-83 |
| src/flync/core/base\_models/unique\_name.py                         |       22 |        1 |     95% |        23 |
| src/flync/core/datatypes/\_\_init\_\_.py                            |        7 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                    |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitrange.py                                |        5 |        0 |    100% |           |
| src/flync/core/datatypes/ipaddress.py                               |       27 |        3 |     89% | 30, 62-63 |
| src/flync/core/datatypes/macaddress.py                              |       23 |        0 |    100% |           |
| src/flync/core/datatypes/value\_range.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                            |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                                |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                                 |      117 |       16 |     86% |31, 33, 36, 42-43, 55-56, 70-78, 273 |
| src/flync/core/utils/common\_validators.py                          |      228 |       36 |     84% |55, 163, 211-214, 294-296, 324, 331, 370, 395, 397, 406, 438, 448, 450, 452, 473, 491, 498, 528, 531, 534, 563, 571, 602, 611, 613, 643, 649, 658, 664, 674, 680 |
| src/flync/core/utils/exceptions.py                                  |       14 |        0 |    100% |           |
| src/flync/core/utils/exceptions\_handling.py                        |      218 |       15 |     93% |25, 55, 77-78, 99, 108, 110, 170, 260-263, 461-464 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py       |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py                  |       60 |        2 |     97% |    53, 58 |
| src/flync/core/version\_migrators/\_\_init\_\_.py                   |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py      |       21 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                     |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                           |       51 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/lin\_bus.py                           |       39 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                       |       13 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                     |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller.py                         |      224 |        8 |     96% |121-122, 365, 431, 435, 449, 454, 456 |
| src/flync/model/flync\_4\_ecu/ecu.py                                |      188 |       17 |     91% |149, 167, 196, 298, 302, 306, 310, 324-330, 338, 371-374 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py                 |      164 |        1 |     99% |        51 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                     |       24 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py           |       27 |        1 |     96% |        89 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py                  |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                                |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                               |       29 |        1 |     97% |        86 |
| src/flync/model/flync\_4\_ecu/router.py                             |       15 |        1 |     93% |        69 |
| src/flync/model/flync\_4\_ecu/socket\_container.py                  |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                            |       91 |        4 |     96% |136-137, 141-142 |
| src/flync/model/flync\_4\_ecu/switch.py                             |      174 |        1 |     99% |       128 |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                        |       26 |        1 |     96% |        56 |
| src/flync/model/flync\_4\_general\_configuration/\_\_init\_\_.py    |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_general\_configuration/flync\_channels.py |       29 |        2 |     93% |   98, 112 |
| src/flync/model/flync\_4\_general\_configuration/flync\_general.py  |       12 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py                  |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                      |       57 |        1 |     98% |        33 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                             |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                      |       38 |        4 |     89% |38, 42, 44, 46 |
| src/flync/model/flync\_4\_security/macsec.py                        |       42 |        2 |     95% |  134, 140 |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                    |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                           |       79 |        1 |     99% |       286 |
| src/flync/model/flync\_4\_signal/pdu.py                             |      110 |        1 |     99% |       311 |
| src/flync/model/flync\_4\_signal/signal.py                          |      130 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                    |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                      |       90 |        2 |     98% |     67-68 |
| src/flync/model/flync\_4\_someip/service\_interface.py              |      236 |       12 |     95% |428-431, 451, 849-850, 894-895, 905-906, 909 |
| src/flync/model/flync\_4\_someip/someip\_datatypes.py               |      188 |        9 |     95% |500, 507-509, 581, 587, 590, 595, 899 |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py                  |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/system\_topology.py              |       57 |        7 |     88% |68, 105, 112, 120, 129, 138, 147 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                                |      226 |       29 |     87% |331-336, 345, 352-362, 366-372, 464, 468, 478, 587, 637, 675, 713, 748, 785, 822 |
| src/flync/model/flync\_4\_tsn/timesync.py                           |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                     |      162 |       31 |     81% |102, 134-135, 155-156, 195, 261, 265-268, 272-275, 279-282, 285, 288, 294, 298-301, 305-308, 312 |
| src/flync/sdk/\_\_init\_\_.py                                       |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                               |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                        |       24 |        2 |     92% |     71-72 |
| src/flync/sdk/context/node\_info.py                                 |        8 |        0 |    100% |           |
| src/flync/sdk/context/workspace\_config.py                          |       21 |        3 |     86% |     69-71 |
| src/flync/sdk/helpers/\_\_init\_\_.py                               |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/generation\_helpers.py                        |      244 |      171 |     30% |44-52, 60, 73-80, 84, 88-103, 107-123, 137, 146-151, 165-173, 189-201, 220-226, 240-246, 255-283, 287-307, 319-322, 334-337, 359-365, 378-388, 393-397, 418-422, 430-448, 460-480 |
| src/flync/sdk/helpers/nodes\_helpers.py                             |       17 |        5 |     71% | 34, 54-57 |
| src/flync/sdk/helpers/validate\_examples.py                         |       13 |       13 |      0% |      8-31 |
| src/flync/sdk/helpers/validate\_workspace.py                        |      109 |      109 |      0% |     9-191 |
| src/flync/sdk/helpers/validation\_helpers.py                        |       48 |       16 |     67% |81, 98-101, 129-149 |
| src/flync/sdk/utils/\_\_init\_\_.py                                 |        0 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                                 |       16 |        2 |     88% |     49-50 |
| src/flync/sdk/utils/model\_dependencies.py                          |      249 |       12 |     95% |94-96, 400, 439, 523-527, 596, 612 |
| src/flync/sdk/utils/sdk\_types.py                                   |        4 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/document.py                                 |       19 |        2 |     89% |     69-70 |
| src/flync/sdk/workspace/flync\_workspace.py                         |      489 |      133 |     73% |158-168, 247, 263-266, 280-289, 308-325, 351-372, 394-404, 419-424, 466-470, 564, 597-612, 629, 665, 828, 890, 944, 1001-1002, 1007, 1009-1014, 1031-1036, 1051-1064, 1086, 1101, 1140-1155, 1428, 1506, 1548, 1567-1576 |
| src/flync/sdk/workspace/ids.py                                      |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                                  |        6 |        0 |    100% |           |
| src/flync/sdk/workspace/source.py                                   |        7 |        0 |    100% |           |
| **TOTAL**                                                           | **4917** |  **690** | **86%** |           |


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