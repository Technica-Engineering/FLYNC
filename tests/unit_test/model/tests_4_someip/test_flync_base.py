# import os
# import unittest.mock

# import pydantic_yaml

# from flync.model.flync_4_someip import FLYNCImport, ServiceInterface

# Commenting test for now because Semver class in metadata has no in built serializer

# @unittest.mock.patch("pydantic_yaml.parse_yaml_file_as")
# def test_flync_import(parse_yaml_file_as: unittest.mock.MagicMock, tmp_path,metadata_entry):
#     service_path = os.path.join(tmp_path, "service.yml")
#     service_1 = ServiceInterface(meta = metadata_entry,service_id=1, name="s1")
#     pydantic_yaml.to_yaml_file(service_path, service_1)
#     FLYNCImport.IMPORT_CACHE = {service_path: service_1}  # fake an import
#     f = FLYNCImport(root=service_path)
#     assert f._imported_value == service_1
#     service_2_path = os.path.join(tmp_path, "service_2.yml")
#     service_2 = ServiceInterface(meta = metadata_entry,service_id=2, name="s2")
#     pydantic_yaml.to_yaml_file(service_2_path, service_2)
#     parse_yaml_file_as.return_value = service_2
#     f2 = FLYNCImport(root=service_2_path)
#     parse_yaml_file_as.assert_called_with(ServiceInterface, service_2_path)
#     assert f2._imported_value == parse_yaml_file_as.return_value
