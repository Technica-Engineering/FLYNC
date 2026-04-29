from flync.sdk.workspace.flync_workspace import FLYNCWorkspace

def update_yaml_content(yaml_file,old_text,new_text):
    with open(yaml_file, 'r+') as file:
            content = file.read()  
            content = content.replace(old_text,new_text)
            file.seek(0)
            file.write(content)  
            file.truncate()

def append_yaml_content(yaml_file,new_text):
    with open(yaml_file, 'a') as file:
        file.write(new_text)

def model_has_socket(loaded_ws: FLYNCWorkspace):
    return any(
        address.sockets
        for ecu in loaded_ws.flync_model.ecus
        for controller in ecu.controllers
        for eth_iface in controller.ethernet_interfaces
        for vlan in eth_iface.interface_config.virtual_interfaces
        for address in vlan.addresses
        )