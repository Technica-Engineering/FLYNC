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
| src/flync/core/datatypes/\_\_init\_\_.py                        |       10 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitmask.py                             |       59 |        1 |     98% |       100 |
| src/flync/core/datatypes/bitrange.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/duration.py                            |       15 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                          |       45 |        1 |     98% |       124 |
| src/flync/core/datatypes/ipaddress.py                           |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                          |       23 |        8 |     65% |16-17, 22-27 |
| src/flync/core/datatypes/value\_range.py                        |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                        |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                            |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                             |      118 |       16 |     86% |31, 33, 36, 42-43, 57-65, 83, 224, 264 |
| src/flync/core/utils/exceptions.py                              |       67 |        4 |     94% |   149-152 |
| src/flync/core/utils/exceptions\_handling.py                    |      279 |       19 |     93% |44, 74, 117, 125, 207-211, 215, 231, 235, 248, 262, 289, 313, 315, 687-689 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py   |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py              |       78 |        8 |     90% |99-100, 110, 183-187 |
| src/flync/core/validators/\_\_init\_\_.py                       |        2 |        0 |    100% |           |
| src/flync/core/validators/address.py                            |       55 |        7 |     87% |71-74, 154-156 |
| src/flync/core/validators/bit\_ranges.py                        |       35 |        1 |     97% |        97 |
| src/flync/core/validators/connection\_compatibility.py          |       91 |       11 |     88% |19, 28, 66, 68, 196, 219-221, 380, 389, 395 |
| src/flync/core/validators/forwarder.py                          |      313 |        7 |     98% |56, 272, 297, 319, 623, 673, 695 |
| src/flync/core/validators/generic.py                            |       80 |        5 |     94% |32, 84, 118, 174, 211 |
| src/flync/core/validators/interface.py                          |       97 |        3 |     97% |45, 172, 207 |
| src/flync/core/validators/state\_management.py                  |      222 |        4 |     98% |296, 439, 550, 614 |
| src/flync/core/validators/traffic\_classes.py                   |       36 |        6 |     83% |15, 21, 30, 36, 50, 56 |
| src/flync/core/version\_migrators/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/legacy\_controller\_check.py  |       17 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                 |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                   |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                  |       20 |        1 |     95% |        44 |
| src/flync/model/flync\_4\_app/application.py                    |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                       |       50 |        1 |     98% |       131 |
| src/flync/model/flync\_4\_bus/lin\_bus.py                       |       35 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/\_\_init\_\_.py         |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/flync\_channels.py      |      121 |        2 |     98% |  223, 277 |
| src/flync/model/flync\_4\_communication/flync\_communication.py |       16 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/\_\_init\_\_.py           |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/diagnostics\_config.py    |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/\_\_init\_\_.py      |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/deployment.py        |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/doip\_config.py      |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/timings.py           |       23 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/\_\_init\_\_.py       |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/data\_identifier.py   |       46 |        1 |     98% |        85 |
| src/flync/model/flync\_4\_diagnostics/uds/datatypes.py          |       59 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/dtc.py                |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/routine.py            |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/server.py             |      195 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/services.py           |      161 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/subfunctions.py       |       35 |        1 |     97% |       273 |
| src/flync/model/flync\_4\_diagnostics/uds/timings.py            |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/uds\_config.py        |       47 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                   |       22 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                 |       44 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/compute\_node.py                  |       47 |        5 |     89% |122-125, 130 |
| src/flync/model/flync\_4\_ecu/controller.py                     |      223 |        5 |     98% |245, 265, 267, 364, 687 |
| src/flync/model/flync\_4\_ecu/controller\_interface.py          |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller\_topology.py           |       17 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/ecu.py                            |      295 |        5 |     98% |331, 373, 530, 593-594 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py             |      206 |        4 |     98% |51, 481-483 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                 |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py       |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py              |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                            |       74 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                           |       36 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/router.py                         |       23 |        1 |     96% |        92 |
| src/flync/model/flync\_4\_ecu/socket\_container.py              |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                        |      121 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                         |      252 |        5 |     98% |142, 180, 565, 782-783 |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                    |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/\_\_init\_\_.py       |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/instrumentation.py    |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/measurement\_point.py |      150 |        3 |     98% |101, 105, 109 |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py              |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                  |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/state\_management.py               |       90 |        2 |     98% |   419-420 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                         |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                  |       38 |        4 |     89% |38, 44, 46, 48 |
| src/flync/model/flync\_4\_security/macsec.py                    |       64 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                   |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                       |       92 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                         |       85 |        2 |     98% |  295, 298 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py             |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                      |      161 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py             |       94 |        1 |     99% |       127 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                  |       83 |        1 |     99% |       190 |
| src/flync/model/flync\_4\_someip/service\_interface.py          |      223 |        4 |     98% |401, 596, 877, 915 |
| src/flync/model/flync\_4\_someip/someip\_complex\_datatypes.py  |       49 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/someip\_simple\_datatypes.py   |      147 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py              |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/bus\_topology.py             |      120 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/ethernet\_multidrop.py       |      214 |       11 |     95% |97-99, 141, 256, 304, 362, 382, 399, 445, 497 |
| src/flync/model/flync\_4\_topology/ethernet\_topology.py        |      101 |        7 |     93% |106, 130, 230, 259-260, 271-272 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                            |      225 |        9 |     96% |345-350, 359, 368, 374, 479 |
| src/flync/model/flync\_4\_tsn/timesync.py                       |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                 |      574 |       25 |     96% |107, 111, 121, 137, 384, 392, 406-421, 438-439, 463-464, 477-478, 491, 709, 913, 920, 945, 1010 |
| src/flync/sdk/\_\_init\_\_.py                                   |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                    |       29 |        2 |     93% |     91-92 |
| src/flync/sdk/context/node\_info.py                             |        9 |        1 |     89% |        41 |
| src/flync/sdk/context/workspace\_config.py                      |      118 |       18 |     85% |69-74, 150, 163, 171-179, 214, 220, 224, 266, 288, 309 |
| src/flync/sdk/helpers/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/debug.py                                  |      115 |        3 |     97% |74-75, 222 |
| src/flync/sdk/helpers/debug\_layers/\_\_init\_\_.py             |        2 |        0 |    100% |           |
| src/flync/sdk/helpers/debug\_layers/layer1\_structure.py        |      129 |        4 |     97% |64-65, 216, 235 |
| src/flync/sdk/helpers/debug\_layers/layer2\_yaml.py             |       42 |        4 |     90% |39-41, 71-72 |
| src/flync/sdk/helpers/debug\_layers/layer3\_4\_5\_workspace.py  |      233 |       62 |     73% |105, 124, 154, 276-277, 413-414, 424, 427, 431, 436, 448-449, 455-463, 475-476, 486-489, 491, 507, 509, 513, 519-536, 547-557, 562-571 |
| src/flync/sdk/helpers/debug\_layers/runner.py                   |      123 |        8 |     93% |59, 67, 144-146, 183, 208-209 |
| src/flync/sdk/helpers/generation\_helpers.py                    |      425 |       32 |     92% |58, 63, 85, 143, 365, 410-411, 443-447, 463, 465-466, 491, 515, 578-580, 641, 650, 705-706, 760, 777, 865, 875, 922, 935-936, 944 |
| src/flync/sdk/helpers/nodes\_helpers.py                         |       17 |        1 |     94% |        55 |
| src/flync/sdk/helpers/validation\_helpers.py                    |       60 |       11 |     82% |   147-167 |
| src/flync/sdk/utils/\_\_init\_\_.py                             |        1 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                             |       15 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                      |      293 |       22 |     92% |73, 97-99, 157, 232, 381, 439, 463, 553-557, 579, 638, 655, 673, 722-726, 762-763 |
| src/flync/sdk/utils/model\_dumper.py                            |       31 |        2 |     94% |     50-51 |
| src/flync/sdk/utils/model\_schema.py                            |      116 |        2 |     98% |   64, 266 |
| src/flync/sdk/utils/sdk\_types.py                               |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/\_base.py                               |      108 |       23 |     79% |173, 188, 227-240, 255-258, 273-276 |
| src/flync/sdk/workspace/\_incremental.py                        |      220 |       23 |     90% |63, 65-67, 105, 108, 131, 150-152, 180, 288, 292, 304, 307-309, 380, 426-430 |
| src/flync/sdk/workspace/\_loading.py                            |      271 |       19 |     93% |55, 257, 345-361, 379, 425, 594, 633, 672, 700, 761-762, 774 |
| src/flync/sdk/workspace/\_object\_mapping.py                    |      243 |       21 |     91% |122-123, 422, 515-524, 561, 568, 588-590, 625, 628, 637, 653, 681 |
| src/flync/sdk/workspace/\_saving.py                             |      105 |       12 |     89% |69, 90, 164, 169, 177, 228-233, 277, 284 |
| src/flync/sdk/workspace/document.py                             |       65 |        2 |     97% |   174-175 |
| src/flync/sdk/workspace/flync\_workspace.py                     |       47 |        3 |     94% |59, 62, 120 |
| src/flync/sdk/workspace/ids.py                                  |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                              |       95 |        3 |     97% |   166-169 |
| src/flync/sdk/workspace/source.py                               |       11 |        0 |    100% |           |
| src/flync\_cli/\_\_init\_\_.py                                  |        2 |        0 |    100% |           |
| src/flync\_cli/commands/config.py                               |       29 |        0 |    100% |           |
| src/flync\_cli/commands/errors.py                               |      101 |        6 |     94% |134, 143, 146, 165, 176, 178 |
| src/flync\_cli/commands/filetree.py                             |       30 |        0 |    100% |           |
| src/flync\_cli/commands/generate\_system\_uml.py                |      409 |        8 |     98% |188, 212-213, 385, 388, 406, 481, 524 |
| src/flync\_cli/commands/info.py                                 |      264 |        2 |     99% |  142, 348 |
| src/flync\_cli/commands/schema.py                               |       16 |        0 |    100% |           |
| src/flync\_cli/commands/validate.py                             |       39 |        0 |    100% |           |
| src/flync\_cli/convert\_puml.py                                 |       69 |        0 |    100% |           |
| src/flync\_cli/main.py                                          |       50 |        0 |    100% |           |
| src/flync\_cli/utils/console.py                                 |        4 |        0 |    100% |           |
| src/flync\_cli/utils/deprecation.py                             |        3 |        0 |    100% |           |
| src/flync\_cli/utils/error\_renumber.py                         |      180 |       11 |     94% |92-93, 112-113, 125-126, 197, 249, 280, 284-285 |
| src/flync\_cli/utils/error\_table.py                            |       90 |        6 |     93% |   168-174 |
| src/flync\_cli/utils/errors.py                                  |      152 |        3 |     98% |65, 152, 271 |
| src/flync\_cli/utils/mapping.py                                 |        3 |        0 |    100% |           |
| src/flync\_cli/utils/model\_views.py                            |      101 |        4 |     96% |97-98, 133, 149 |
| src/flync\_cli/utils/styles.py                                  |       31 |        0 |    100% |           |
| src/flync\_cli/utils/workspace.py                               |       49 |        2 |     96% |     30-31 |
| src/flync\_converter/\_\_init\_\_.py                            |       51 |        0 |    100% |           |
| src/flync\_converter/\_\_main\_\_.py                            |        2 |        2 |      0% |       3-4 |
| src/flync\_converter/base/\_\_init\_\_.py                       |        5 |        0 |    100% |           |
| src/flync\_converter/base/base\_converter.py                    |       35 |        0 |    100% |           |
| src/flync\_converter/base/converter\_config.py                  |       78 |        1 |     99% |       183 |
| src/flync\_converter/base/converter\_report.py                  |       40 |        0 |    100% |           |
| src/flync\_converter/base/reporters.py                          |       25 |        0 |    100% |           |
| src/flync\_converter/cli/\_\_init\_\_.py                        |       21 |        0 |    100% |           |
| src/flync\_converter/cli/\_optional.py                          |       16 |        0 |    100% |           |
| src/flync\_converter/cli/commands.py                            |       84 |        0 |    100% |           |
| src/flync\_converter/cli/dynamic.py                             |       46 |        0 |    100% |           |
| src/flync\_converter/cli/group.py                               |       17 |        0 |    100% |           |
| src/flync\_converter/cli/gui/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync\_converter/cli/gui/app.py                             |      113 |       12 |     89% |126-128, 140, 145, 179-180, 189-193 |
| src/flync\_converter/cli/gui/widgets/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/flync\_converter/cli/gui/widgets/converter\_panel.py        |      193 |       13 |     93% |33-34, 124-126, 161, 199-201, 262, 291-293 |
| src/flync\_converter/cli/gui/widgets/log\_handler.py            |       15 |        2 |     87% |     37-38 |
| src/flync\_converter/cli/interactive.py                         |       72 |        0 |    100% |           |
| src/flync\_converter/cli/tui/\_\_init\_\_.py                    |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/app.py                             |       91 |       91 |      0% |     3-198 |
| src/flync\_converter/cli/tui/utils.py                           |        2 |        2 |      0% |       3-5 |
| src/flync\_converter/cli/tui/widgets/\_\_init\_\_.py            |        3 |        3 |      0% |       3-6 |
| src/flync\_converter/cli/tui/widgets/converter\_panel.py        |      102 |      102 |      0% |     3-207 |
| src/flync\_converter/cli/tui/widgets/log\_handler.py            |       17 |       17 |      0% |      3-34 |
| src/flync\_converter/cli/types.py                               |       32 |        0 |    100% |           |
| src/flync\_converter/converters/\_\_init\_\_.py                 |        5 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/\_\_init\_\_.py             |       10 |        1 |     90% |        23 |
| src/flync\_converter/converters/dbc/converter.py                |       33 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/dbc\_config.py              |        6 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/decoder.py                  |      207 |        6 |     97% |68, 139, 185, 215, 317-318 |
| src/flync\_converter/converters/dbc/encoder.py                  |      179 |        8 |     96% |43, 67, 175-176, 200-201, 357, 359 |
| src/flync\_converter/converters/dbc/loading.py                  |       49 |        0 |    100% |           |
| src/flync\_converter/converters/flync\_converter.py             |       51 |        1 |     98% |       123 |
| src/flync\_converter/converters/helpers.py                      |       20 |        0 |    100% |           |
| src/flync\_converter/converters/json\_converter.py              |       59 |        8 |     86% |45-47, 60, 77, 89, 106, 121 |
| src/flync\_converter/converters/yaml\_converter.py              |       60 |        8 |     87% |46-48, 61, 79, 91, 110, 125 |
| src/flync\_converter/hookspec.py                                |        4 |        0 |    100% |           |
| src/flync\_converter/registry.py                                |       32 |       19 |     41% |23-30, 37-49, 56-59 |
| src/flync\_converter/reporting.py                               |      103 |        0 |    100% |           |
| src/flync\_converter/utils.py                                   |       75 |        4 |     95% |63-64, 93-94 |
| **TOTAL**                                                       | **13490** |  **824** | **94%** |           |


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