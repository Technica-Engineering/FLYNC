# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                            |    Stmts |     Miss |   Cover |   Missing |
|---------------------------------------------------------------- | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                       |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                  |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                      |        3 |        0 |    100% |           |
| src/flync/core/annotations/external.py                          |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                           |        9 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                         |       22 |        1 |     95% |        50 |
| src/flync/core/base\_models/\_\_init\_\_.py                     |        2 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                      |        8 |        0 |    100% |           |
| src/flync/core/datatypes/\_\_init\_\_.py                        |       10 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitmask.py                             |       59 |        1 |     98% |       100 |
| src/flync/core/datatypes/bitrange.py                            |        5 |        0 |    100% |           |
| src/flync/core/datatypes/duration.py                            |       15 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                          |       43 |        0 |    100% |           |
| src/flync/core/datatypes/ipaddress.py                           |       26 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                          |       23 |        8 |     65% |16-17, 22-27 |
| src/flync/core/datatypes/value\_range.py                        |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                        |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                            |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                             |      121 |       15 |     88% |39, 41, 44, 50-52, 66-74, 271 |
| src/flync/core/utils/exceptions.py                              |       67 |        4 |     94% |   149-152 |
| src/flync/core/utils/exceptions\_handling.py                    |      281 |       19 |     93% |51, 81, 124, 132, 214-218, 222, 238, 242, 255, 269, 296, 320, 322, 694-696 |
| src/flync/core/utils/multicast/\_\_init\_\_.py                  |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py   |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py              |       85 |        8 |     91% |125-126, 138, 204-208 |
| src/flync/core/utils/yaml\_io.py                                |       17 |        0 |    100% |           |
| src/flync/core/validators/\_\_init\_\_.py                       |        2 |        0 |    100% |           |
| src/flync/core/validators/address.py                            |       54 |        7 |     87% |70-73, 153-155 |
| src/flync/core/validators/bit\_ranges.py                        |       36 |        1 |     97% |        99 |
| src/flync/core/validators/connection\_compatibility.py          |      170 |       14 |     92% |73, 82, 120, 122, 279-281, 440, 449, 455, 615, 680, 713, 728 |
| src/flync/core/validators/forwarder.py                          |      300 |        7 |     98% |61, 259, 284, 306, 611, 662, 684 |
| src/flync/core/validators/generic.py                            |       82 |        5 |     94% |34, 86, 120, 176, 213 |
| src/flync/core/validators/interface.py                          |      102 |        2 |     98% |   47, 208 |
| src/flync/core/validators/state\_management.py                  |      238 |        4 |     98% |320, 471, 582, 648 |
| src/flync/core/validators/traffic\_classes.py                   |       36 |        6 |     83% |22, 28, 37, 42, 56, 61 |
| src/flync/core/version\_migrators/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/\_base.py                     |       57 |        2 |     96% |    92, 95 |
| src/flync/core/version\_migrators/engine.py                     |      222 |       11 |     95% |189, 228, 240, 348, 353-356, 388, 390, 392 |
| src/flync/core/version\_migrators/history.py                    |       42 |        4 |     90% |   122-125 |
| src/flync/core/version\_migrators/legacy\_controller\_check.py  |       17 |        0 |    100% |           |
| src/flync/core/version\_migrators/migrations/\_\_init\_\_.py    |        3 |        0 |    100% |           |
| src/flync/model/\_\_init\_\_.py                                 |        4 |        0 |    100% |           |
| src/flync/model/\_model\_parts/\_\_init\_\_.py                  |        5 |        0 |    100% |           |
| src/flync/model/\_model\_parts/\_accessors.py                   |       86 |        3 |     97% |85, 92, 106 |
| src/flync/model/\_model\_parts/\_binding.py                     |       34 |        0 |    100% |           |
| src/flync/model/\_model\_parts/\_j1939.py                       |       79 |        4 |     95% |70, 74, 84, 100 |
| src/flync/model/\_model\_parts/\_multicast.py                   |      106 |        8 |     92% |82-87, 107-108 |
| src/flync/model/\_model\_parts/\_protocol.py                    |       16 |        0 |    100% |           |
| src/flync/model/\_model\_parts/\_types.py                       |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                   |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                  |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/application.py                    |       26 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                       |       50 |        1 |     98% |       131 |
| src/flync/model/flync\_4\_bus/lin\_bus.py                       |       42 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/\_\_init\_\_.py         |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/flync\_channels.py      |      121 |        2 |     98% |  223, 277 |
| src/flync/model/flync\_4\_communication/flync\_communication.py |       16 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/\_\_init\_\_.py           |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/diagnostics\_config.py    |       22 |        0 |    100% |           |
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
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                   |       24 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                 |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/compute\_node.py                  |       48 |        5 |     90% |128-131, 136 |
| src/flync/model/flync\_4\_ecu/controller.py                     |      225 |        6 |     97% |148, 253, 273, 275, 372, 701 |
| src/flync/model/flync\_4\_ecu/controller\_interface.py          |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller\_topology.py           |       17 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/ecu.py                            |      319 |        5 |     98% |364, 406, 571, 634-635 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py             |      210 |        3 |     99% |   487-489 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                 |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py       |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mii.py                            |      116 |        1 |     99% |       471 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py              |       27 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                            |       54 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                           |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port\_extender.py                 |      138 |        3 |     98% |168, 179, 358 |
| src/flync/model/flync\_4\_ecu/router.py                         |       24 |        1 |     96% |        97 |
| src/flync/model/flync\_4\_ecu/socket\_container.py              |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                        |      123 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                         |      168 |        2 |     99% |  121, 420 |
| src/flync/model/flync\_4\_ecu/switch\_config.py                 |       17 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch\_port.py                   |       67 |        1 |     99% |       177 |
| src/flync/model/flync\_4\_ecu/switch\_tcam.py                   |       90 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                    |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/\_\_init\_\_.py       |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/instrumentation.py    |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/measurement\_point.py |      150 |        3 |     98% |101, 105, 109 |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py              |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                  |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/state\_management.py               |       97 |        2 |     98% |   423-424 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                         |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                  |       38 |        4 |     89% |38, 44, 46, 48 |
| src/flync/model/flync\_4\_security/macsec.py                    |       64 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/can\_frame\_ref.py             |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                   |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                       |       92 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/j1939\_frame\_ref.py           |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                         |       85 |        2 |     98% |  295, 298 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py             |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                      |      160 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py             |       91 |        1 |     99% |       126 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                  |       82 |        1 |     99% |       189 |
| src/flync/model/flync\_4\_someip/service\_interface.py          |      236 |        4 |     98% |400, 600, 897, 935 |
| src/flync/model/flync\_4\_someip/someip\_complex\_datatypes.py  |       50 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/someip\_simple\_datatypes.py   |      147 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py              |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/bus\_topology.py             |      124 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/ethernet\_multidrop.py       |      217 |       11 |     95% |100-102, 144, 259, 307, 365, 385, 404, 450, 502 |
| src/flync/model/flync\_4\_topology/ethernet\_topology.py        |      106 |        8 |     92% |108, 126, 189, 222, 251-252, 263-264 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                            |      232 |        3 |     99% |373, 381, 388 |
| src/flync/model/flync\_4\_tsn/timesync.py                       |       23 |        0 |    100% |           |
| src/flync/model/flync\_model.py                                 |      329 |        9 |     97% |264, 272, 294-295, 319-320, 333-334, 646 |
| src/flync/sdk/\_\_init\_\_.py                                   |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                    |       29 |        2 |     93% |     91-92 |
| src/flync/sdk/context/node\_info.py                             |        9 |        1 |     89% |        41 |
| src/flync/sdk/context/workspace\_config.py                      |      119 |       19 |     84% |69-74, 77-82, 155, 168, 176-184, 219, 225, 229, 300, 321 |
| src/flync/sdk/helpers/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/debug.py                                  |      115 |        3 |     97% |74-75, 222 |
| src/flync/sdk/helpers/debug\_layers/\_\_init\_\_.py             |        2 |        0 |    100% |           |
| src/flync/sdk/helpers/debug\_layers/layer1\_structure.py        |      129 |        4 |     97% |64-65, 216, 235 |
| src/flync/sdk/helpers/debug\_layers/layer2\_yaml.py             |       29 |        2 |     93% |     67-68 |
| src/flync/sdk/helpers/debug\_layers/layer3\_4\_5\_workspace.py  |      233 |       62 |     73% |105, 124, 154, 276-277, 413-414, 424, 427, 431, 436, 448-449, 455-463, 475-476, 486-489, 491, 507, 509, 513, 519-536, 547-557, 562-571 |
| src/flync/sdk/helpers/debug\_layers/runner.py                   |      123 |        8 |     93% |59, 67, 144-146, 183, 208-209 |
| src/flync/sdk/helpers/generation\_helpers.py                    |      425 |       32 |     92% |58, 63, 85, 143, 365, 410-411, 443-447, 463, 465-466, 491, 515, 578-580, 641, 650, 705-706, 760, 777, 865, 875, 922, 935-936, 944 |
| src/flync/sdk/helpers/nodes\_helpers.py                         |       17 |        1 |     94% |        55 |
| src/flync/sdk/helpers/validation\_helpers.py                    |       60 |       11 |     82% |   147-167 |
| src/flync/sdk/utils/\_\_init\_\_.py                             |        1 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                             |       15 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                      |      294 |       22 |     93% |74, 98-100, 158, 233, 382, 440, 464, 554-558, 580, 639, 656, 679, 728-732, 768-769 |
| src/flync/sdk/utils/model\_dumper.py                            |       31 |        2 |     94% |     50-51 |
| src/flync/sdk/utils/model\_schema.py                            |      116 |        2 |     98% |   64, 266 |
| src/flync/sdk/utils/sdk\_types.py                               |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                         |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/\_base.py                               |      113 |       24 |     79% |178, 193, 208, 247-260, 275-278, 293-296 |
| src/flync/sdk/workspace/\_incremental.py                        |      220 |       23 |     90% |63, 65-67, 105, 108, 131, 150-152, 180, 288, 292, 304, 307-309, 380, 426-430 |
| src/flync/sdk/workspace/\_loading.py                            |      280 |       21 |     92% |70, 274, 362-380, 398, 444, 613, 652, 691, 719, 780-781, 793 |
| src/flync/sdk/workspace/\_object\_mapping.py                    |      238 |       21 |     91% |121-122, 421, 495-504, 541, 548, 568-570, 605, 608, 617, 633, 661 |
| src/flync/sdk/workspace/\_saving.py                             |      126 |       12 |     90% |114, 135, 209, 214, 222, 273-278, 322, 329 |
| src/flync/sdk/workspace/document.py                             |       65 |        4 |     94% |108-109, 174-175 |
| src/flync/sdk/workspace/flync\_workspace.py                     |       50 |        3 |     94% |59, 62, 120 |
| src/flync/sdk/workspace/ids.py                                  |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                              |       95 |        3 |     97% |   166-169 |
| src/flync/sdk/workspace/source.py                               |       11 |        0 |    100% |           |
| src/flync\_cli/\_\_init\_\_.py                                  |        2 |        0 |    100% |           |
| src/flync\_cli/commands/config.py                               |       29 |        0 |    100% |           |
| src/flync\_cli/commands/errors.py                               |      101 |        6 |     94% |134, 143, 146, 165, 176, 178 |
| src/flync\_cli/commands/filetree.py                             |       30 |        0 |    100% |           |
| src/flync\_cli/commands/generate\_system\_uml.py                |      410 |        8 |     98% |188, 212-213, 385, 388, 406, 481, 524 |
| src/flync\_cli/commands/info.py                                 |      264 |        2 |     99% |  142, 348 |
| src/flync\_cli/commands/migrate.py                              |       62 |        6 |     90% |63-69, 119-121 |
| src/flync\_cli/commands/schema.py                               |       16 |        0 |    100% |           |
| src/flync\_cli/commands/validate.py                             |       48 |        2 |     96% |   104-105 |
| src/flync\_cli/convert\_puml.py                                 |       69 |        0 |    100% |           |
| src/flync\_cli/main.py                                          |       52 |        0 |    100% |           |
| src/flync\_cli/utils/console.py                                 |        4 |        0 |    100% |           |
| src/flync\_cli/utils/deprecation.py                             |        3 |        0 |    100% |           |
| src/flync\_cli/utils/error\_renumber.py                         |      180 |       11 |     94% |92-93, 112-113, 125-126, 197, 249, 280, 284-285 |
| src/flync\_cli/utils/error\_table.py                            |       90 |        6 |     93% |   168-174 |
| src/flync\_cli/utils/errors.py                                  |      152 |        3 |     98% |65, 152, 271 |
| src/flync\_cli/utils/mapping.py                                 |        3 |        0 |    100% |           |
| src/flync\_cli/utils/model\_views.py                            |      103 |        4 |     96% |97-98, 133, 149 |
| src/flync\_cli/utils/styles.py                                  |       31 |        0 |    100% |           |
| src/flync\_cli/utils/workspace.py                               |       49 |        2 |     96% |     30-31 |
| src/flync\_converter/\_\_init\_\_.py                            |      105 |        0 |    100% |           |
| src/flync\_converter/\_\_main\_\_.py                            |        2 |        2 |      0% |       3-4 |
| src/flync\_converter/base/\_\_init\_\_.py                       |        5 |        0 |    100% |           |
| src/flync\_converter/base/base\_converter.py                    |       35 |        0 |    100% |           |
| src/flync\_converter/base/converter\_config.py                  |       81 |        1 |     99% |       200 |
| src/flync\_converter/base/converter\_report.py                  |       40 |        0 |    100% |           |
| src/flync\_converter/base/reporters.py                          |       25 |        0 |    100% |           |
| src/flync\_converter/cli/\_\_init\_\_.py                        |       21 |        0 |    100% |           |
| src/flync\_converter/cli/\_optional.py                          |       16 |        0 |    100% |           |
| src/flync\_converter/cli/commands.py                            |      107 |        0 |    100% |           |
| src/flync\_converter/cli/dynamic.py                             |       73 |        0 |    100% |           |
| src/flync\_converter/cli/group.py                               |       22 |        0 |    100% |           |
| src/flync\_converter/cli/gui/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync\_converter/cli/gui/app.py                             |      136 |        7 |     95% |170-172, 184, 189, 227-228 |
| src/flync\_converter/cli/gui/widgets/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/flync\_converter/cli/gui/widgets/converter\_panel.py        |      193 |       13 |     93% |33-34, 124-126, 161, 199-201, 262, 291-293 |
| src/flync\_converter/cli/gui/widgets/log\_handler.py            |       15 |        2 |     87% |     37-38 |
| src/flync\_converter/cli/interactive.py                         |       72 |        0 |    100% |           |
| src/flync\_converter/cli/preview.py                             |       60 |        0 |    100% |           |
| src/flync\_converter/cli/tui/\_\_init\_\_.py                    |        2 |        0 |    100% |           |
| src/flync\_converter/cli/tui/app.py                             |      121 |        7 |     94% |134-138, 163, 236-237, 242-243 |
| src/flync\_converter/cli/tui/utils.py                           |        2 |        0 |    100% |           |
| src/flync\_converter/cli/tui/widgets/\_\_init\_\_.py            |        3 |        0 |    100% |           |
| src/flync\_converter/cli/tui/widgets/converter\_panel.py        |      103 |        6 |     94% |25-26, 88, 153-156 |
| src/flync\_converter/cli/tui/widgets/log\_handler.py            |       19 |        5 |     74% | 29, 33-37 |
| src/flync\_converter/cli/types.py                               |       32 |        0 |    100% |           |
| src/flync\_converter/conversion\_request.py                     |       84 |        1 |     99% |        81 |
| src/flync\_converter/converters/\_\_init\_\_.py                 |        5 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/\_\_init\_\_.py             |       10 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/converter.py                |       33 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/dbc\_config.py              |        6 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/decoder.py                  |      277 |       11 |     96% |71, 142, 188, 218, 268-269, 372, 450-456 |
| src/flync\_converter/converters/dbc/encoder.py                  |      211 |        7 |     97% |88, 196-197, 221-222, 476, 478 |
| src/flync\_converter/converters/dbc/loading.py                  |       59 |        0 |    100% |           |
| src/flync\_converter/converters/flync\_converter.py             |       51 |        0 |    100% |           |
| src/flync\_converter/converters/helpers.py                      |       20 |        0 |    100% |           |
| src/flync\_converter/converters/json\_converter.py              |       59 |        7 |     88% |45-47, 60, 77, 89, 106 |
| src/flync\_converter/converters/yaml\_converter.py              |       60 |        7 |     88% |45-47, 60, 78, 90, 109 |
| src/flync\_converter/hookspec.py                                |        4 |        0 |    100% |           |
| src/flync\_converter/model\_merger.py                           |      142 |        1 |     99% |       153 |
| src/flync\_converter/registry.py                                |       32 |        5 |     84% | 30, 56-59 |
| src/flync\_converter/reporting.py                               |      177 |        5 |     97% |303, 358-360, 362 |
| src/flync\_converter/utils.py                                   |       75 |        4 |     95% |63-64, 93-94 |
| **TOTAL**                                                       | **15173** |  **637** | **96%** |           |


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