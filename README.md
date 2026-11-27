# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/Technica-Engineering/FLYNC/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                              |    Stmts |     Miss |   Cover |   Missing |
|------------------------------------------------------------------ | -------: | -------: | ------: | --------: |
| src/flync/\_\_init\_\_.py                                         |        2 |        0 |    100% |           |
| src/flync/core/\_\_init\_\_.py                                    |        0 |        0 |    100% |           |
| src/flync/core/annotations/\_\_init\_\_.py                        |        4 |        0 |    100% |           |
| src/flync/core/annotations/external.py                            |       18 |        0 |    100% |           |
| src/flync/core/annotations/implied.py                             |        9 |        0 |    100% |           |
| src/flync/core/annotations/namespaced.py                          |        5 |        0 |    100% |           |
| src/flync/core/annotations/reference.py                           |       22 |        1 |     95% |        50 |
| src/flync/core/base\_models/\_\_init\_\_.py                       |        3 |        0 |    100% |           |
| src/flync/core/base\_models/base\_model.py                        |        8 |        0 |    100% |           |
| src/flync/core/base\_models/namespace.py                          |       11 |        0 |    100% |           |
| src/flync/core/datatypes/\_\_init\_\_.py                          |       10 |        0 |    100% |           |
| src/flync/core/datatypes/base.py                                  |       10 |        0 |    100% |           |
| src/flync/core/datatypes/bitmask.py                               |       59 |        1 |     98% |       100 |
| src/flync/core/datatypes/bitrange.py                              |        5 |        0 |    100% |           |
| src/flync/core/datatypes/duration.py                              |       15 |        0 |    100% |           |
| src/flync/core/datatypes/ethertypes.py                            |       43 |        0 |    100% |           |
| src/flync/core/datatypes/ipaddress.py                             |       27 |        0 |    100% |           |
| src/flync/core/datatypes/macaddress.py                            |       23 |        8 |     65% |16-17, 22-27 |
| src/flync/core/datatypes/value\_range.py                          |        5 |        0 |    100% |           |
| src/flync/core/datatypes/value\_table.py                          |        5 |        0 |    100% |           |
| src/flync/core/utils/\_\_init\_\_.py                              |        0 |        0 |    100% |           |
| src/flync/core/utils/base\_utils.py                               |      121 |       15 |     88% |39, 41, 44, 50-52, 66-74, 271 |
| src/flync/core/utils/exceptions.py                                |       80 |        4 |     95% |   150-153 |
| src/flync/core/utils/exceptions\_handling.py                      |      268 |       12 |     96% |51, 81, 124, 132, 233, 247, 274, 298, 300, 672-674 |
| src/flync/core/utils/model\_mixins/\_\_init\_\_.py                |        4 |        0 |    100% |           |
| src/flync/core/utils/model\_mixins/accessors.py                   |       86 |        3 |     97% |85, 92, 106 |
| src/flync/core/utils/model\_mixins/binding.py                     |       34 |        0 |    100% |           |
| src/flync/core/utils/model\_mixins/multicast.py                   |      124 |        2 |     98% |   141-142 |
| src/flync/core/utils/model\_mixins/protocol.py                    |       17 |        0 |    100% |           |
| src/flync/core/utils/model\_mixins/types.py                       |        7 |        0 |    100% |           |
| src/flync/core/utils/multicast/\_\_init\_\_.py                    |        3 |        0 |    100% |           |
| src/flync/core/utils/multicast/group\_membership\_handlers.py     |       44 |        0 |    100% |           |
| src/flync/core/utils/multicast/multicast\_paths.py                |       85 |        8 |     91% |125-126, 138, 204-208 |
| src/flync/core/utils/yaml\_io.py                                  |       70 |        1 |     99% |        97 |
| src/flync/core/validators/\_\_init\_\_.py                         |        2 |        0 |    100% |           |
| src/flync/core/validators/address.py                              |       54 |        7 |     87% |70-73, 153-155 |
| src/flync/core/validators/app\_references.py                      |      116 |        0 |    100% |           |
| src/flync/core/validators/bit\_ranges.py                          |       36 |        1 |     97% |        99 |
| src/flync/core/validators/connection\_compatibility.py            |      188 |       14 |     93% |73, 82, 120, 122, 307-309, 468, 477, 483, 644, 709, 775, 790 |
| src/flync/core/validators/forwarder.py                            |      300 |        7 |     98% |61, 259, 284, 306, 611, 662, 684 |
| src/flync/core/validators/generic.py                              |       82 |        4 |     95% |34, 120, 176, 213 |
| src/flync/core/validators/interface.py                            |      210 |        5 |     98% |51, 217, 227, 236, 311 |
| src/flync/core/validators/j1939.py                                |       55 |        4 |     93% |39, 43, 53, 69 |
| src/flync/core/validators/state\_management.py                    |      238 |        4 |     98% |320, 471, 582, 648 |
| src/flync/core/validators/traffic\_classes.py                     |       36 |        6 |     83% |22, 28, 37, 42, 56, 61 |
| src/flync/core/version\_migrators/\_\_init\_\_.py                 |        0 |        0 |    100% |           |
| src/flync/core/version\_migrators/\_base.py                       |       57 |        2 |     96% |    92, 95 |
| src/flync/core/version\_migrators/engine.py                       |      217 |       10 |     95% |185, 234, 342, 347-350, 377, 379, 381 |
| src/flync/core/version\_migrators/history.py                      |       41 |        4 |     90% |   120-123 |
| src/flync/core/version\_migrators/legacy\_controller\_check.py    |       17 |        0 |    100% |           |
| src/flync/core/version\_migrators/migrations/\_\_init\_\_.py      |        5 |        0 |    100% |           |
| src/flync/core/version\_migrators/migrations/v0\_14\_to\_0\_15.py |      123 |        0 |    100% |           |
| src/flync/core/version\_migrators/migrations/v0\_15\_to\_0\_16.py |       65 |        1 |     98% |        27 |
| src/flync/model/\_\_init\_\_.py                                   |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/\_\_init\_\_.py                     |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/app\_bindings.py                    |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/application.py                      |       62 |        2 |     97% |  163, 188 |
| src/flync/model/flync\_4\_app/ipc.py                              |       12 |        0 |    100% |           |
| src/flync/model/flync\_4\_app/signal\_refs.py                     |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/\_\_init\_\_.py                     |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/can\_bus.py                         |       48 |        0 |    100% |           |
| src/flync/model/flync\_4\_bus/lin\_bus.py                         |       42 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/\_\_init\_\_.py           |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_communication/flync\_channels.py        |      132 |        2 |     98% |  238, 292 |
| src/flync/model/flync\_4\_communication/flync\_communication.py   |       16 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/\_\_init\_\_.py             |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/diagnostics\_config.py      |       22 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/\_\_init\_\_.py        |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/deployment.py          |       40 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/doip\_config.py        |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/doip/timings.py             |       23 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/\_\_init\_\_.py         |       10 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/data\_identifier.py     |       46 |        1 |     98% |        85 |
| src/flync/model/flync\_4\_diagnostics/uds/datatypes.py            |       59 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/dtc.py                  |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/routine.py              |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/server.py               |      195 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/services.py             |      161 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/subfunctions.py         |       35 |        1 |     97% |       273 |
| src/flync/model/flync\_4\_diagnostics/uds/timings.py              |       19 |        0 |    100% |           |
| src/flync/model/flync\_4\_diagnostics/uds/uds\_config.py          |       47 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/\_\_init\_\_.py                     |       24 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/can\_interface.py                   |       53 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/compute\_node.py                    |       48 |        5 |     90% |128-131, 136 |
| src/flync/model/flync\_4\_ecu/controller.py                       |      233 |        9 |     96% |150, 255, 275, 277, 374, 714-717 |
| src/flync/model/flync\_4\_ecu/controller\_interface.py            |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/controller\_topology.py             |       17 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/ecu.py                              |      346 |        5 |     99% |412, 457, 622, 685-686 |
| src/flync/model/flync\_4\_ecu/internal\_topology.py               |      222 |       13 |     94% |88, 135, 141, 225, 231, 415, 483, 491, 502-504, 558, 566 |
| src/flync/model/flync\_4\_ecu/lin\_interface.py                   |       48 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mac\_multicast\_endpoint.py         |       20 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/mii.py                              |      144 |        1 |     99% |       571 |
| src/flync/model/flync\_4\_ecu/multicast\_groups.py                |       28 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/phy.py                              |       54 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port.py                             |       45 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/port\_extender.py                   |      138 |        3 |     98% |171, 182, 361 |
| src/flync/model/flync\_4\_ecu/router.py                           |       24 |        1 |     96% |        97 |
| src/flync/model/flync\_4\_ecu/socket\_container.py                |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/sockets.py                          |      123 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch.py                           |      168 |        2 |     99% |  121, 420 |
| src/flync/model/flync\_4\_ecu/switch\_config.py                   |       17 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/switch\_port.py                     |       67 |        1 |     99% |       178 |
| src/flync/model/flync\_4\_ecu/switch\_tcam.py                     |       90 |        0 |    100% |           |
| src/flync/model/flync\_4\_ecu/vlan\_entry.py                      |       29 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/\_\_init\_\_.py         |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/instrumentation.py      |       11 |        0 |    100% |           |
| src/flync/model/flync\_4\_instrumentation/measurement\_point.py   |      150 |        3 |     98% |101, 105, 109 |
| src/flync/model/flync\_4\_metadata/\_\_init\_\_.py                |        3 |        0 |    100% |           |
| src/flync/model/flync\_4\_metadata/metadata.py                    |       57 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/\_\_init\_\_.py                      |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_nm/state\_management.py                 |       97 |        2 |     98% |   423-424 |
| src/flync/model/flync\_4\_safety/\_\_init\_\_.py                  |        2 |        0 |    100% |           |
| src/flync/model/flync\_4\_safety/e2e.py                           |        5 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/\_\_init\_\_.py                |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_security/firewall.py                    |       38 |        4 |     89% |38, 44, 46, 48 |
| src/flync/model/flync\_4\_security/macsec.py                      |       64 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/\_\_init\_\_.py                  |        7 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/can\_frame\_ref.py               |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/forwarder.py                     |       41 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/frame.py                         |       99 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/j1939\_frame\_ref.py             |       18 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/pdu.py                           |       85 |        2 |     98% |  295, 298 |
| src/flync/model/flync\_4\_signal/pdu\_deployment.py               |        9 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/signal.py                        |      160 |        0 |    100% |           |
| src/flync/model/flync\_4\_signal/value\_encoding.py               |       91 |        1 |     99% |       126 |
| src/flync/model/flync\_4\_someip/\_\_init\_\_.py                  |        8 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/deployment.py                    |       82 |        1 |     99% |       189 |
| src/flync/model/flync\_4\_someip/service\_interface.py            |      268 |        4 |     99% |409, 609, 947, 985 |
| src/flync/model/flync\_4\_someip/someip\_complex\_datatypes.py    |       50 |        0 |    100% |           |
| src/flync/model/flync\_4\_someip/someip\_simple\_datatypes.py     |      147 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/\_\_init\_\_.py                |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_topology/bus\_topology.py               |      143 |        1 |     99% |       393 |
| src/flync/model/flync\_4\_topology/ethernet\_multidrop.py         |      217 |       11 |     95% |100-102, 144, 259, 307, 365, 385, 404, 450, 502 |
| src/flync/model/flync\_4\_topology/ethernet\_topology.py          |      106 |        4 |     96% |108, 126, 189, 222 |
| src/flync/model/flync\_4\_tsn/\_\_init\_\_.py                     |        4 |        0 |    100% |           |
| src/flync/model/flync\_4\_tsn/qos.py                              |      232 |        3 |     99% |373, 381, 388 |
| src/flync/model/flync\_4\_tsn/timesync.py                         |       23 |        0 |    100% |           |
| src/flync/model/flync\_4\_variability/\_\_init\_\_.py             |        6 |        0 |    100% |           |
| src/flync/model/flync\_4\_variability/analysis.py                 |       85 |        4 |     95% |74, 125, 129-130 |
| src/flync/model/flync\_4\_variability/condition.py                |      186 |        3 |     98% |235, 267, 382 |
| src/flync/model/flync\_4\_variability/context.py                  |      119 |        1 |     99% |       287 |
| src/flync/model/flync\_4\_variability/feature\_model.py           |      151 |        3 |     98% |36, 73, 395 |
| src/flync/model/flync\_4\_variability/resolution.py               |      210 |        4 |     98% |112, 115, 206-207 |
| src/flync/model/flync\_4\_variability/variant.py                  |       94 |        1 |     99% |       248 |
| src/flync/model/flync\_model.py                                   |      326 |        9 |     97% |330-331, 355-356, 370-371, 516, 518, 664 |
| src/flync/sdk/\_\_init\_\_.py                                     |        0 |        0 |    100% |           |
| src/flync/sdk/context/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/context/diagnostics\_result.py                      |       42 |        2 |     95% |     94-95 |
| src/flync/sdk/context/node\_info.py                               |        9 |        1 |     89% |        41 |
| src/flync/sdk/context/workspace\_config.py                        |      117 |       18 |     85% |69-74, 77-82, 155, 168, 176-184, 219, 225, 229, 300 |
| src/flync/sdk/helpers/\_\_init\_\_.py                             |        0 |        0 |    100% |           |
| src/flync/sdk/helpers/debug.py                                    |      115 |        3 |     97% |74-75, 222 |
| src/flync/sdk/helpers/debug\_layers/\_\_init\_\_.py               |        2 |        0 |    100% |           |
| src/flync/sdk/helpers/debug\_layers/layer1\_structure.py          |      137 |        3 |     98% |65-66, 250 |
| src/flync/sdk/helpers/debug\_layers/layer2\_yaml.py               |       25 |        2 |     92% |     55-56 |
| src/flync/sdk/helpers/debug\_layers/layer3\_4\_5\_workspace.py    |      236 |       62 |     74% |114, 133, 163, 285-286, 423-424, 434, 437, 441, 446, 458-459, 465-473, 485-486, 496-499, 501, 517, 519, 523, 529-546, 557-567, 572-581 |
| src/flync/sdk/helpers/debug\_layers/runner.py                     |      137 |        8 |     94% |61, 69, 168-170, 209, 234-235 |
| src/flync/sdk/helpers/generation\_helpers.py                      |      484 |       32 |     93% |64, 69, 91, 150, 420, 465-466, 498-502, 518, 520-521, 546, 570, 633-635, 726, 735, 790-791, 845, 862, 1065, 1073, 1109, 1122-1123, 1131 |
| src/flync/sdk/helpers/nodes\_helpers.py                           |       17 |        1 |     94% |        55 |
| src/flync/sdk/helpers/validation\_helpers.py                      |      100 |       18 |     82% |194, 199-201, 220-222, 247-267 |
| src/flync/sdk/helpers/variant\_helpers.py                         |       24 |        2 |     92% |     47-48 |
| src/flync/sdk/utils/\_\_init\_\_.py                               |        1 |        0 |    100% |           |
| src/flync/sdk/utils/field\_utils.py                               |       15 |        0 |    100% |           |
| src/flync/sdk/utils/model\_dependencies.py                        |      294 |       22 |     93% |74, 98-100, 158, 233, 382, 440, 464, 554-558, 580, 639, 656, 679, 728-732, 768-769 |
| src/flync/sdk/utils/model\_dumper.py                              |       31 |        2 |     94% |     50-51 |
| src/flync/sdk/utils/model\_schema.py                              |      162 |        3 |     98% |65, 255, 361 |
| src/flync/sdk/utils/sdk\_types.py                                 |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/\_\_init\_\_.py                           |        0 |        0 |    100% |           |
| src/flync/sdk/workspace/\_base.py                                 |      149 |       25 |     83% |204, 261, 278, 293, 331-344, 359-362, 377-380 |
| src/flync/sdk/workspace/\_incremental.py                          |      251 |       25 |     90% |78-81, 94-95, 148, 151, 174, 193-195, 223, 331, 335, 347, 350-352, 423, 474-478 |
| src/flync/sdk/workspace/\_loading.py                              |      320 |       24 |     92% |55, 204, 406-417, 435, 496, 499, 513-518, 703, 742, 776, 895, 958-959, 972 |
| src/flync/sdk/workspace/\_object\_mapping.py                      |      242 |       23 |     90% |123-124, 423, 497-506, 543, 550, 570-572, 586-587, 612, 615, 624, 640, 668 |
| src/flync/sdk/workspace/\_saving.py                               |      127 |       12 |     91% |112, 133, 210, 215, 223, 284-289, 333, 340 |
| src/flync/sdk/workspace/\_variants.py                             |      176 |        5 |     97% |137, 205-206, 225, 348 |
| src/flync/sdk/workspace/document.py                               |       43 |        4 |     91% |74-75, 128-129 |
| src/flync/sdk/workspace/flync\_workspace.py                       |       54 |        3 |     94% |59, 62, 124 |
| src/flync/sdk/workspace/ids.py                                    |        3 |        0 |    100% |           |
| src/flync/sdk/workspace/objects.py                                |       95 |        3 |     97% |   166-169 |
| src/flync/sdk/workspace/source.py                                 |       11 |        0 |    100% |           |
| src/flync/sdk/workspace/variant\_view.py                          |       25 |        0 |    100% |           |
| src/flync\_cli/\_\_init\_\_.py                                    |        2 |        0 |    100% |           |
| src/flync\_cli/commands/config.py                                 |       30 |        0 |    100% |           |
| src/flync\_cli/commands/errors.py                                 |      101 |        6 |     94% |134, 143, 146, 165, 176, 178 |
| src/flync\_cli/commands/filetree.py                               |       30 |        0 |    100% |           |
| src/flync\_cli/commands/generate\_system\_uml.py                  |      410 |        8 |     98% |188, 212-213, 385, 388, 406, 481, 524 |
| src/flync\_cli/commands/info.py                                   |      265 |        2 |     99% |  143, 349 |
| src/flync\_cli/commands/migrate.py                                |       62 |        6 |     90% |63-69, 119-121 |
| src/flync\_cli/commands/schema.py                                 |       16 |        0 |    100% |           |
| src/flync\_cli/commands/validate.py                               |       60 |        4 |     93% |30-31, 147-148 |
| src/flync\_cli/commands/variants.py                               |      205 |       10 |     95% |51-53, 67, 69, 328-330, 332-333 |
| src/flync\_cli/convert\_puml.py                                   |       69 |        0 |    100% |           |
| src/flync\_cli/main.py                                            |       54 |        0 |    100% |           |
| src/flync\_cli/utils/console.py                                   |        8 |        0 |    100% |           |
| src/flync\_cli/utils/deprecation.py                               |        3 |        0 |    100% |           |
| src/flync\_cli/utils/error\_renumber.py                           |      180 |       11 |     94% |92-93, 112-113, 125-126, 197, 249, 280, 284-285 |
| src/flync\_cli/utils/error\_table.py                              |      150 |       12 |     92% |145, 156, 180-186, 233-235, 247 |
| src/flync\_cli/utils/errors.py                                    |      152 |        3 |     98% |65, 152, 271 |
| src/flync\_cli/utils/mapping.py                                   |        3 |        0 |    100% |           |
| src/flync\_cli/utils/model\_views.py                              |      104 |        4 |     96% |98-99, 134, 150 |
| src/flync\_cli/utils/styles.py                                    |       32 |        0 |    100% |           |
| src/flync\_cli/utils/workspace.py                                 |       51 |        2 |     96% |     40-41 |
| src/flync\_converter/\_\_init\_\_.py                              |      105 |        0 |    100% |           |
| src/flync\_converter/\_\_main\_\_.py                              |        2 |        2 |      0% |       3-4 |
| src/flync\_converter/base/\_\_init\_\_.py                         |        5 |        0 |    100% |           |
| src/flync\_converter/base/base\_converter.py                      |       35 |        0 |    100% |           |
| src/flync\_converter/base/converter\_config.py                    |       81 |        1 |     99% |       200 |
| src/flync\_converter/base/converter\_report.py                    |       40 |        0 |    100% |           |
| src/flync\_converter/base/reporters.py                            |       25 |        0 |    100% |           |
| src/flync\_converter/cli/\_\_init\_\_.py                          |       21 |        0 |    100% |           |
| src/flync\_converter/cli/\_optional.py                            |       16 |        0 |    100% |           |
| src/flync\_converter/cli/commands.py                              |      203 |        2 |     99% |  313, 315 |
| src/flync\_converter/cli/dynamic.py                               |      116 |        0 |    100% |           |
| src/flync\_converter/cli/group.py                                 |       22 |        0 |    100% |           |
| src/flync\_converter/cli/gui/\_\_init\_\_.py                      |        2 |        0 |    100% |           |
| src/flync\_converter/cli/gui/app.py                               |      153 |        8 |     95% |173-175, 218-220, 252-253 |
| src/flync\_converter/cli/gui/widgets/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync\_converter/cli/gui/widgets/converter\_panel.py          |      236 |        9 |     96% |34-35, 263-265, 326, 356-358 |
| src/flync\_converter/cli/gui/widgets/converter\_panel\_list.py    |       67 |        1 |     99% |        83 |
| src/flync\_converter/cli/gui/widgets/log\_handler.py              |       15 |        2 |     87% |     37-38 |
| src/flync\_converter/cli/interactive.py                           |       77 |        0 |    100% |           |
| src/flync\_converter/cli/preview.py                               |       58 |        0 |    100% |           |
| src/flync\_converter/cli/tui/\_\_init\_\_.py                      |        2 |        0 |    100% |           |
| src/flync\_converter/cli/tui/app.py                               |      174 |       15 |     91% |139-140, 192-193, 247-250, 264-266, 327-328, 333-334 |
| src/flync\_converter/cli/tui/utils.py                             |        2 |        0 |    100% |           |
| src/flync\_converter/cli/tui/widgets/\_\_init\_\_.py              |        4 |        0 |    100% |           |
| src/flync\_converter/cli/tui/widgets/converter\_panel.py          |      183 |        9 |     95% |53, 203, 260, 319-322, 346, 350, 357 |
| src/flync\_converter/cli/tui/widgets/converter\_panel\_list.py    |       57 |        1 |     98% |        91 |
| src/flync\_converter/cli/tui/widgets/log\_handler.py              |       19 |        5 |     74% | 29, 33-37 |
| src/flync\_converter/cli/tui/widgets/path\_picker.py              |       89 |       21 |     76% |37-38, 127, 153, 157-162, 165-166, 171-174, 177-178, 181-182, 187 |
| src/flync\_converter/cli/types.py                                 |      104 |        0 |    100% |           |
| src/flync\_converter/conversion\_request.py                       |       84 |        1 |     99% |        81 |
| src/flync\_converter/converters/\_\_init\_\_.py                   |        5 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/\_\_init\_\_.py               |       10 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/converter.py                  |       33 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/dbc\_config.py                |        6 |        0 |    100% |           |
| src/flync\_converter/converters/dbc/decoder.py                    |      275 |       11 |     96% |71, 142, 188, 218, 268-269, 367, 445-451 |
| src/flync\_converter/converters/dbc/encoder.py                    |      208 |        7 |     97% |83, 191-192, 216-217, 470, 472 |
| src/flync\_converter/converters/dbc/loading.py                    |       59 |        0 |    100% |           |
| src/flync\_converter/converters/flync\_converter.py               |       57 |        0 |    100% |           |
| src/flync\_converter/converters/helpers.py                        |       20 |        0 |    100% |           |
| src/flync\_converter/converters/json\_converter.py                |       59 |        7 |     88% |45-47, 60, 77, 89, 106 |
| src/flync\_converter/converters/yaml\_converter.py                |       60 |        7 |     88% |45-47, 60, 78, 90, 109 |
| src/flync\_converter/hookspec.py                                  |        4 |        0 |    100% |           |
| src/flync\_converter/model\_merger.py                             |      142 |        1 |     99% |       153 |
| src/flync\_converter/registry.py                                  |       32 |        5 |     84% | 30, 56-59 |
| src/flync\_converter/reporting.py                                 |      177 |        5 |     97% |303, 358-360, 362 |
| src/flync\_converter/utils.py                                     |       75 |        4 |     95% |63-64, 93-94 |
| **TOTAL**                                                         | **18195** |  **726** | **96%** |           |


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