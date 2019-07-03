# Skippy Daemon
K8s daemon which automatically labels the nodes with their capabilities.
f.e. an NVidia Tegra TX2 with Cuda V10 will automatically be assigned the "capability.skippy.io: nvidia-cuda-10" label.

`kubectl apply -f k8s-skippy-daemon.yaml`