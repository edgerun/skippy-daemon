import argparse
import json
import logging
import os
import time
from typing import Dict
import re
from shutil import which

from kubernetes import config, client
from kubernetes.client import V1Node
from kubernetes.client.rest import ApiException


def get_cuda_version(api: client.CoreV1Api, node_name: str) -> (str, str):
    # Set the label "capability.skippy.io/nvidia-cuda" with the version of CUDA as a value (if installed)
    try:
        with open('/usr/local/cuda/version.txt', 'r') as version_file:
            version_str = version_file.read()
            version_re = re.search(r'^CUDA Version ([0-9]+).[0-9]+.[0-9]+', version_str)
            if len(version_re.groups()) == 1:
                version = version_re.group(1)
                logging.debug('capability.skippy.io/nvidia-cuda: Found NVidia CUDA Version %s', version)
                return 'capability.skippy.io/nvidia-cuda', version
    except FileNotFoundError:
        pass

    logging.debug('capability.skippy.io/nvidia-cuda: No valid /usr/local/cuda/version.txt found. '
                  'Assuming no CUDA installed.')
    return 'capability.skippy.io/nvidia-cuda', None


def check_nvidia_gpu(api: client.CoreV1Api, node_name: str) -> (str, str):
    # Set the label "capability.skippy.io/nvidia-gpu" if the binary "nvidia-smi" is found
    if which('nvidia-smi'):
        logging.debug('capability.skippy.io/nvidia-gpu: Found nvidia-smi')
        return 'capability.skippy.io/nvidia-gpu', ''
    else:
        logging.debug('capability.skippy.io/nvidia-gpu: No nvidia-smi available. Assuming no NVidia GPU')
        return 'capability.skippy.io/nvidia-gpu', None


def edge_label(api: client.CoreV1Api, node_name: str) -> (str, str):
    # Set the edge label if no locality type is set yet.
    status: V1Node = api.read_node(node_name)
    try:
        # noinspection PyStatementEffect
        status.metadata.labels['locality.skippy.io/type']
        logging.debug('locality.skippy.io/type: Already present, not doing anything here...')
    except KeyError:
        logging.debug('locality.skippy.io/type: Not yet set. Using default value (edge).')
        return 'locality.skippy.io/type', 'edge'


def storage_node_label(api: client.CoreV1Api, node_name: str) -> (str, str):
    # Set the edge label if no locality type is set yet.
    field_selector = 'spec.nodeName=' + node_name
    label_selector = 'app=minio'
    pods = api.list_pod_for_all_namespaces(watch=False, field_selector=field_selector, label_selector=label_selector)
    if len(pods.items) > 0:
        logging.debug('data.skippy.io/storage-node: Found a storage pod on the node. Setting label.')
        return 'data.skippy.io/storage-node', ''
    else:
        logging.debug('data.skippy.io/storage-node: No storage pod found on the node. Removing label.')
        return 'data.skippy.io/storage-node', None


labelling_functions = [get_cuda_version, check_nvidia_gpu, edge_label, storage_node_label]


def set_labels(api: client.CoreV1Api, node_name: str, labels: Dict[str, str]):
    try:
        logging.info(f'Updating labels for node {node_name}: {labels}...')
        body = {
            "metadata": {
                "labels": labels
            }
        }
        api.patch_node(node_name, body)
        logging.info('Update was successful.')
    except ApiException as e:
        # Parse the JSON message body of the exception
        logging.exception('ApiExceptionMessage: %s', json.loads(e.body)['message'])
        raise e


def main():
    # Parse the arguments
    parser = argparse.ArgumentParser(description='Skippy Daemon - Doing the dirty work away from the spotlight')
    parser.add_argument('-c', '--kube-config', action='store_true', dest='kube_config',
                        help='Load kube-config from home dir instead of in-cluster-config from envs.', default=False)
    parser.add_argument('-n', '--node', action='store', dest='node_name',
                        help='Node name to use (instead of environment variable NODE_NAME)')
    parser.add_argument('-d', '--debug', action='store_true', dest='debug',
                        help='Enable debug logs.', default=False)
    args = parser.parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    node_name = args.node_name

    # Set the log level
    logging.getLogger().setLevel(level)

    # Load the kubernetes API config
    if args.kube_config:
        # Load the configuration from ~/.kube
        logging.debug('Loading kube config...')
        config.load_kube_config()
    else:
        # Load the configuration when running inside the cluster (by reading envs set by k8s)
        logging.debug('Loading in-cluster config...')
        config.load_incluster_config()

    api = client.CoreV1Api()

    old_labels = None
    while True:
        try:
            if node_name is None:
                node_name = os.environ['NODE_NAME']

            # Create the dict with all labels
            labels = {}
            for fn in labelling_functions:
                label = fn(api, node_name)
                if label is not None:
                    labels[label[0]] = label[1]

            # Only patch the labels if they've changed
            if labels != old_labels:
                # Set the labels on the current node
                set_labels(api, node_name, labels)
                old_labels = labels
            else:
                logging.debug('Labels have not changed. No update necessary.')
        except KeyError:
            logging.exception('The name of the node could not be found! '
                              'Make sure to expose spec.nodeName as env var NODE_NAME.')

        # Wait for an hour until we re-check the node caps
        logging.debug('Waiting for 1 hour until re-check.')
        time.sleep(3600)


if __name__ == '__main__':
    main()

