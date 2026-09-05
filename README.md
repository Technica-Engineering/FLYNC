# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                       |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                  |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/annotations/external.py                          |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                           |        9 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                         |       21 |        1 |     95% |        48 |
| src/flync/core/base\_models/\_\_init\_\_.py                     |        2 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                      |        7 |        0 |    100% |           |
| src/flync/core/datatypes/\_\_init\_\_.py                        |        9 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitmask.py                             |       59 |        1 |     98% |       100 |
| src/flync/core/datatypes/bitrange.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                          |       45 |        1 |     98% |       124 |
| src/flync/core/datatypes/ipaddress.py                           |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                          |       23 |        0 |    100% |           |
| src/flync/core/datatypes/value\_range.py                        |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                        |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                            |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                             |      118 |       16 |     86% |31, 33, 36, 42-43, 57-65, 83, 224, 264 |
| src/flync/core/utils/exceptions.py                              |       62 |        0 |    100% |           |
| src/flync/core/utils/exceptions\_handling.py                    |      233 |       18 |     92% |43, 73, 100, 108, 157-161, 165, 178, 182, 198, 225, 249, 251, 589-591 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py   |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py              |       62 |        3 |     95% |63, 68, 78 |
| src/flync/core/validators/\_\_init\_\_.py                       |        2 |        0 |    100% |           |
| src/flync/core/validators/address.py                            |       55 |        7 |     87% |71-74, 154-156 |
| src/flync/core/validators/bit\_ranges.py                        |       35 |        1 |     97% |        97 |
| src/flync/core/validators/connection\_compatibility.py          |       95 |       10 |     89% |19, 28, 66, 68, 196, 218, 225, 384, 393, 399 |
| src/flync/core/validators/forwarder.py                          |      310 |        7 |     98% |55, 268, 293, 315, 619, 669, 691 |
| src/flync/core/validators/generic.py                            |       80 |        4 |     95% |32, 84, 174, 211 |
| src/flync/core/validators/interface.py                          |       71 |        2 |     97% |   45, 153 |
| src/flync/core/validators/state\_management.py                  |      222 |        4 |     98% |296, 439, 548, 612 |
| src/flync/core/validators/traffic\_classes.py                   |       36 |        6 |     83% |15, 21, 30, 36, 50, 56 |
| src/flync/core/version\_migrators/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py  |       17 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                 |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                   |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                  |       20 |        1 |     95% |        44 |
| src/flync/model/flync\_4\_app/application.py                    |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                       |       48 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/lin\_bus.py                       |       42 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/\_\_init\_\_.py         |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/flync\_channels.py      |      121 |        2 |     98% |  223, 277 |
| src/flync/model/flync\_4\_communication/flync\_communication.py |       14 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                   |       15 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                 |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller.py                     |      276 |        7 |     97% |428, 432, 450, 455, 457, 563, 802 |
| src/flync/model/flync\_4\_ecu/controller\_interface.py          |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/ecu.py                            |      296 |        6 |     98% |295, 330, 372, 521, 581-582 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py             |      210 |       10 |     95% |51, 216-217, 475-476, 486-488, 546-547 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                 |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py       |       27 |        1 |     96% |        88 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py              |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                            |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                           |       29 |        1 |     97% |        86 |
| src/flync/model/flync\_4\_ecu/router.py                         |       22 |        1 |     95% |        91 |
| src/flync/model/flync\_4\_ecu/socket\_container.py              |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                        |      110 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                         |      240 |        6 |     98% |143, 181, 566, 727, 758-759 |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                    |       27 |        1 |     96% |        57 |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py              |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                  |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/state\_management.py               |       90 |        2 |     98% |   415-416 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                         |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                  |       38 |        4 |     89% |38, 44, 46, 48 |
| src/flync/model/flync\_4\_security/macsec.py                    |       70 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                   |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                       |       68 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                         |       91 |        2 |     98% |  302, 305 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py             |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                      |      160 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py             |       94 |        1 |     99% |       127 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                  |       79 |        1 |     99% |       176 |
| src/flync/model/flync\_4\_someip/service\_interface.py          |      218 |        3 |     99% |400, 595, 860 |
| src/flync/model/flync\_4\_someip/someip\_complex\_datatypes.py  |       50 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/someip\_simple\_datatypes.py   |      149 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/bus\_topology.py             |       94 |        1 |     99% |       272 |
| src/flync/model/flync\_4\_topology/ethernet\_topology.py        |       70 |        6 |     91% |61, 65, 104, 110, 128, 146 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                            |      228 |        9 |     96% |350-355, 364, 373, 379, 484 |
| src/flync/model/flync\_4\_tsn/timesync.py                       |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                 |      356 |       20 |     94% |220, 228, 242-257, 274-275, 299-300, 324-325, 373, 402, 557, 563, 577 |
| src/flync/sdk/\_\_init\_\_.py                                   |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                    |       29 |        2 |     93% |     91-92 |
| src/flync/sdk/context/node\_info.py                             |        9 |        1 |     89% |        41 |
| src/flync/sdk/context/workspace\_config.py                      |      118 |       18 |     85% |69-74, 150, 163, 171-179, 214, 220, 224, 266, 288, 309 |
| src/flync/sdk/helpers/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/debug.py                                  |      112 |        3 |     97% |74-75, 210 |
| src/flync/sdk/helpers/debug\_layers/\_\_init\_\_.py             |        2 |        0 |    100% |           |
| src/flync/sdk/helpers/debug\_layers/layer1\_structure.py        |      129 |        4 |     97% |64-65, 216, 235 |
| src/flync/sdk/helpers/debug\_layers/layer2\_yaml.py             |       42 |        4 |     90% |39-41, 71-72 |
| src/flync/sdk/helpers/debug\_layers/layer3\_4\_5\_workspace.py  |      233 |       58 |     75% |105, 124, 154, 276-277, 413-414, 424, 427, 431, 436, 448-449, 455-463, 475-476, 489, 509, 513, 519-536, 547-557, 562-571 |
| src/flync/sdk/helpers/debug\_layers/runner.py                   |      123 |        8 |     93% |59, 67, 144-146, 183, 208-209 |
| src/flync/sdk/helpers/generation\_helpers.py                    |      425 |       32 |     92% |58, 63, 85, 143, 365, 410-411, 443-447, 463, 465-466, 491, 515, 578-580, 641, 650, 705-706, 760, 777, 865, 875, 922, 935-936, 944 |
| src/flync/sdk/helpers/nodes\_helpers.py                         |       17 |        1 |     94% |        55 |
| src/flync/sdk/helpers/validation\_helpers.py                    |       48 |       11 |     77% |   126-146 |
| src/flync/sdk/utils/\_\_init\_\_.py                             |        1 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                             |       15 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                      |      292 |       22 |     92% |73, 97-99, 157, 232, 381, 430, 454, 544-548, 570, 629, 646, 664, 713-717, 753-754 |
| src/flync/sdk/utils/model\_dumper.py                            |       31 |        2 |     94% |     50-51 |
| src/flync/sdk/utils/sdk\_types.py                               |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/\_base.py                               |      106 |       23 |     78% |166, 181, 220-233, 248-251, 266-269 |
| src/flync/sdk/workspace/\_incremental.py                        |      221 |       23 |     90% |64, 66-68, 106, 109, 132, 151-153, 181, 289, 293, 305, 308-310, 381, 427-431 |
| src/flync/sdk/workspace/\_loading.py                            |      253 |       20 |     92% |54, 262, 295-311, 329, 375, 543, 582, 621, 649, 710-711, 721, 723 |
| src/flync/sdk/workspace/\_object\_mapping.py                    |      242 |       20 |     92% |122-123, 421, 514-523, 560, 587-589, 624, 627, 636, 652, 680 |
| src/flync/sdk/workspace/\_saving.py                             |      103 |       12 |     88% |69, 90, 164, 169, 177, 224-229, 273, 280 |
| src/flync/sdk/workspace/document.py                             |       58 |        2 |     97% |   160-161 |
| src/flync/sdk/workspace/flync\_workspace.py                     |       46 |        3 |     93% |58, 61, 119 |
| src/flync/sdk/workspace/ids.py                                  |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                              |       95 |        3 |     97% |   166-169 |
| src/flync/sdk/workspace/source.py                               |       11 |        0 |    100% |           |
| src/flync\_cli/\_\_init\_\_.py                                  |        2 |        0 |    100% |           |
| src/flync\_cli/commands/config.py                               |       29 |        0 |    100% |           |
| src/flync\_cli/commands/errors.py                               |       43 |        0 |    100% |           |
| src/flync\_cli/commands/filetree.py                             |       29 |        0 |    100% |           |
| src/flync\_cli/commands/generate\_system\_uml.py                |      365 |        6 |     98% |187, 211-212, 384, 387, 405 |
| src/flync\_cli/commands/info.py                                 |      264 |        2 |     99% |  142, 348 |
| src/flync\_cli/commands/validate.py                             |       39 |        0 |    100% |           |
| src/flync\_cli/convert\_puml.py                                 |       69 |        0 |    100% |           |
| src/flync\_cli/main.py                                          |       48 |        0 |    100% |           |
| src/flync\_cli/utils/console.py                                 |        4 |        0 |    100% |           |
| src/flync\_cli/utils/deprecation.py                             |        3 |        0 |    100% |           |
| src/flync\_cli/utils/error\_table.py                            |       90 |        6 |     93% |   168-174 |
| src/flync\_cli/utils/errors.py                                  |      122 |        2 |     98% |   63, 210 |
| src/flync\_cli/utils/mapping.py                                 |        3 |        0 |    100% |           |
| src/flync\_cli/utils/model\_views.py                            |      101 |        4 |     96% |87-88, 123, 139 |
| src/flync\_cli/utils/styles.py                                  |       31 |        0 |    100% |           |
| src/flync\_cli/utils/workspace.py                               |       49 |        2 |     96% |     30-31 |
| src/flync\_converter/\_\_init\_\_.py                            |       34 |        0 |    100% |           |
| src/flync\_converter/\_\_main\_\_.py                            |        2 |        2 |      0% |       3-4 |
| src/flync\_converter/base/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync\_converter/base/base\_converter.py                    |       15 |        0 |    100% |           |
| src/flync\_converter/base/converter\_config.py                  |        2 |        0 |    100% |           |
| src/flync\_converter/cli/\_\_init\_\_.py                        |       21 |        0 |    100% |           |
| src/flync\_converter/cli/\_optional.py                          |       16 |        0 |    100% |           |
| src/flync\_converter/cli/commands.py                            |       74 |        0 |    100% |           |
| src/flync\_converter/cli/dynamic.py                             |       39 |        0 |    100% |           |
| src/flync\_converter/cli/group.py                               |       17 |        0 |    100% |           |
| src/flync\_converter/cli/gui/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync\_converter/cli/gui/app.py                             |      113 |       12 |     89% |126-128, 140, 145, 179-180, 189-193 |
| src/flync\_converter/cli/gui/widgets/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/flync\_converter/cli/gui/widgets/converter\_panel.py        |      130 |       10 |     92% |29-30, 111-113, 145, 166, 168-170 |
| src/flync\_converter/cli/gui/widgets/log\_handler.py            |       15 |        2 |     87% |     37-38 |
| src/flync\_converter/cli/interactive.py                         |       59 |        0 |    100% |           |
| src/flync\_converter/cli/tui/\_\_init\_\_.py                    |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/app.py                             |       91 |       91 |      0% |     3-198 |
| src/flync\_converter/cli/tui/utils.py                           |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/widgets/\_\_init\_\_.py            |        3 |        3 |      0% |       3-6 |
| src/flync\_converter/cli/tui/widgets/converter\_panel.py        |       97 |       97 |      0% |     3-199 |
| src/flync\_converter/cli/tui/widgets/log\_handler.py            |       17 |       17 |      0% |      3-34 |
| src/flync\_converter/cli/types.py                               |       32 |        0 |    100% |           |
| src/flync\_converter/converters/\_\_init\_\_.py                 |        5 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/\_\_init\_\_.py             |       10 |        1 |     90% |        23 |
| src/flync\_converter/converters/dbc/converter.py                |       30 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/dbc\_config.py              |        6 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/decoder.py                  |      199 |       14 |     93% |66, 75, 77, 79, 81, 123-124, 126, 131, 163, 191, 287, 408-413 |
| src/flync\_converter/converters/dbc/encoder.py                  |      140 |        5 |     96% |38, 62, 164-165, 188 |
| src/flync\_converter/converters/dbc/loading.py                  |       41 |        0 |    100% |           |
| src/flync\_converter/converters/flync\_converter.py             |       28 |        1 |     96% |        68 |
| src/flync\_converter/converters/helpers.py                      |        4 |        0 |    100% |           |
| src/flync\_converter/converters/json\_converter.py              |       49 |        5 |     90% |43, 59, 71, 86, 101 |
| src/flync\_converter/converters/yaml\_converter.py              |       49 |        5 |     90% |44, 60, 72, 87, 102 |
| src/flync\_converter/hookspec.py                                |        4 |        0 |    100% |           |
| src/flync\_converter/registry.py                                |       32 |       19 |     41% |23-30, 37-49, 56-59 |
| src/flync\_converter/utils.py                                   |       75 |        4 |     95% |63-64, 93-94 |
| **TOTAL**                                                       | **10913** |  **752** | **93%** |           |


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