import time
import requests
from src.consul_service_info import ConsulServiceInfo
from src.haproxy_service_info import HaproxyServiceInfo
from src.haproxy_service_action import HaproxyServiceAction
import socket
import sys

consul_server_address = sys.argv[0]
consul_service_name = sys.argv[1]
haproxy_socket_host = sys.argv[2]
haproxy_socket_port = sys.argv[3]
backend_name = sys.argv[4]


def execute_haproxy_command(haproxy_socket_host, haproxy_socket_port, command):
    haproxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    haproxy_socket.settimeout(20)

    haproxy_socket.connect((haproxy_socket_host, haproxy_socket_port))
    haproxy_socket.send(command.encode())
    response = ''
    try:
        while True:
            buf = haproxy_socket.recv(16)
            if buf:
                response += buf.decode('utf-8')
            else:
                break
    finally:
        haproxy_socket.shutdown(socket.SHUT_WR)
        time.sleep(0.5)
        haproxy_socket.close()
    return response


def fetch_all_haproxy_stats(haproxy_socket_host, haproxy_socket_port):
    return execute_haproxy_command(haproxy_socket_host, haproxy_socket_port, "show stat\n")


def fetch_all_available_consul_services(consul_server, consul_service_name, print_info):
    consul_services_json = requests.get(consul_server + "/v1/catalog/service/" + consul_service_name)
    consul_services_json.raise_for_status()
    consul_services = consul_services_json.json()

    if print_info:
        print('***** CONSUL SERVICE(S) FETCHED *****', end="\n\n")

    consul_services_dict = {}
    for consul_service in consul_services:
        consul_service_info = ConsulServiceInfo(consul_service["ServiceID"],
                                                consul_service["ServiceAddress"],
                                                consul_service["ServicePort"])
        consul_services_dict[consul_service_info.address] = consul_service_info

        if print_info:
            print('id: ' + consul_service_info.id)
            print('host: ' + consul_service_info.host)
            print('port: ' + str(consul_service_info.port), end="\n\n")

    return consul_services_dict


def get_all_haproxy_services(haproxy_slots, print_info):
    haproxy_active_services = []
    haproxy_inactive_services = []

    if print_info:
        print('***** HAPROXY SERVICE(S) FETCHED *****', end="\n\n")

    for slot in haproxy_slots:
        slot_values = slot.split(",")
        if len(slot_values) < 80 or slot_values[0] != backend_name or slot_values[1] == 'BACKEND':
            continue

        haproxy_service_info = HaproxyServiceInfo(slot_values[1], slot_values[73], slot_values[17])

        if print_info:
            print('id: ' + haproxy_service_info.id)
            print('host: ' + haproxy_service_info.host)
            print('port: ' + str(haproxy_service_info.port))
            print('status: ' + haproxy_service_info.status, end="\n\n")

        if haproxy_service_info.is_active():
            haproxy_active_services.append(haproxy_service_info)
        else:
            haproxy_inactive_services.append(haproxy_service_info)

    return haproxy_active_services, haproxy_inactive_services


def calculate_haproxy_service_actions(consul_services_dict,
                                      haproxy_active_services,
                                      haproxy_inactive_services):
    haproxy_service_actions = []

    for i, haproxy_service_info in enumerate(haproxy_inactive_services):
        if consul_services_dict.get(haproxy_service_info.address, None) is not None:
            haproxy_service_action = HaproxyServiceAction(haproxy_service_info.id,
                                                          haproxy_service_info.host,
                                                          haproxy_service_info.port,
                                                          'ENABLE')
            del consul_services_dict[haproxy_service_info.address]
            del haproxy_inactive_services[i]
            haproxy_service_actions.append(haproxy_service_action)

    haproxy_disable_service_actions = []
    for haproxy_service_info in haproxy_active_services:
        if consul_services_dict.get(haproxy_service_info.address, None) is None:
            haproxy_inactive_services.append(haproxy_service_info)
            haproxy_service_action = HaproxyServiceAction(haproxy_service_info.id,
                                                          haproxy_service_info.host,
                                                          haproxy_service_info.port,
                                                          'DISABLE')
            haproxy_disable_service_actions.append(haproxy_service_action)
        else:
            del consul_services_dict[haproxy_service_info.address]

    for address, consul_service_info in consul_services_dict.items():
        if len(haproxy_inactive_services) == 0:
            if len(haproxy_disable_service_actions) == 0:
                print('Error: Haproxy has no slot left for new service at '+consul_service_info.address)
            else:
                suitable_service_id = haproxy_inactive_services.pop(0).id
                haproxy_service_action = HaproxyServiceAction(suitable_service_id,
                                                              consul_service_info.host,
                                                              consul_service_info.port,
                                                              'NEW')
                haproxy_service_actions.append(haproxy_service_action)
        else:
            suitable_service_id = haproxy_inactive_services.pop(0).id
            haproxy_service_action = HaproxyServiceAction(suitable_service_id,
                                                          consul_service_info.host,
                                                          consul_service_info.port,
                                                          'NEW')
            haproxy_service_actions.append(haproxy_service_action)

    haproxy_service_actions += haproxy_disable_service_actions

    return haproxy_service_actions


def execute_haproxy_service_actions(haproxy_service_actions):
    print('START UPDATING HAPROXY CONFIGURATION...')
    for haproxy_service_action in haproxy_service_actions:
        if haproxy_service_action.action == 'DISABLE':
            execute_haproxy_command(haproxy_socket_host, haproxy_socket_port,
                                    'set server ' + backend_name + '/' + haproxy_service_action.id +
                                    ' state maint\n')
            print('DISABLE '+haproxy_service_action.id+' '+haproxy_service_action.address)

        elif haproxy_service_action.action == 'ENABLE':
            execute_haproxy_command(haproxy_socket_host, haproxy_socket_port,
                                    'set server ' + backend_name + '/' + haproxy_service_action.id +
                                    ' state ready\n')
            print('ENABLE '+haproxy_service_action.id+' '+haproxy_service_action.address)

        elif haproxy_service_action.action == 'NEW':
            execute_haproxy_command(haproxy_socket_host, haproxy_socket_port,
                                    'set server ' + backend_name + '/' + haproxy_service_action.id +
                                    ' addr ' + haproxy_service_action.host +
                                    ' port ' + str(haproxy_service_action.port) + '\n')

            execute_haproxy_command(haproxy_socket_host, haproxy_socket_port,
                                    'set server ' + backend_name + '/' + haproxy_service_action.id +
                                    ' state ready\n')

            print('NEW '+haproxy_service_action.id+' '+haproxy_service_action.address)


if __name__ == "__main__":
    consul_services_dict = fetch_all_available_consul_services(consul_server_address, consul_service_name, True)

    haproxy_stats = fetch_all_haproxy_stats(haproxy_socket_host, haproxy_socket_port)
    if not haproxy_stats:
        print('Failed to fetch all backend service from haproxy via socket: '
              + haproxy_socket_host + ':' + str(haproxy_socket_port))
        sys.exit(-1)
    haproxy_slots = haproxy_stats.split('\n')

    (haproxy_active_services, haproxy_inactive_services) = get_all_haproxy_services(haproxy_slots, True)

    haproxy_service_actions = calculate_haproxy_service_actions(consul_services_dict,
                                                                haproxy_active_services,
                                                                haproxy_inactive_services)

    execute_haproxy_service_actions(haproxy_service_actions)

