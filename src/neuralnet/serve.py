# Listens on UDP port 3333
# Accept request packets of size 1 + imcount*6400
# byte one is image count
# followed are grayscale 80x80 image chunks
# reply is a vector of imcount size with values 0 or 1 depending on the class found


import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision
import torchvision.datasets as datasets
import torchvision.transforms as transforms
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

import sys
import socket


if len(sys.argv) != 2:
    print("USAGE: serve.py MODELFILE")
    sys.exit(1)

class Net(nn.Module):

    def __init__(self):
        super(Net, self).__init__()
        # 1 input image channel, 6 output channels, 3x3 square convolution
        # kernel
        self.conv1 = nn.Conv2d(1, 6, 3)
        self.conv2 = nn.Conv2d(6, 16, 3)
        # an affine operation: y = Wx + b
        self.fc1 = nn.Linear(5184, 120)  # 6*6 from image dimension
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 2)

    def forward(self, x):
        # Max pooling over a (2, 2) window
        x = F.max_pool2d(F.relu(self.conv1(x)), (2, 2))
        # If the size is a square you can only specify a single number
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)
        x = x.view(-1, self.num_flat_features(x))
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

    def num_flat_features(self, x):
        size = x.size()[1:]  # all dimensions except the batch dimension
        num_features = 1
        for s in size:
            num_features *= s
        return num_features


net = Net()
print(net)
net.load_state_dict(torch.load(sys.argv[1]))

transform = transforms.Compose(
    [transforms.Grayscale(num_output_channels=1),
     transforms.ToTensor(),
     transforms.Normalize((0.5), (0.5))])

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('127.0.0.1', 3333))

while True:
    data, addr = sock.recvfrom(65535)
    img_count = int(data[0])
    images = []
    for i in range(img_count):
        ima = Image.frombytes('L', (80, 80), data[1+i*80*80:1+(i+1)*80*80], 'raw')
        ima = transform(ima)
        images.append(ima)
    #tens = torch.Tensor(img_count, 1, 80, 80)
    #torch.cat(images, out=tens)
    tens = torch.stack(images)
    outputs = net(tens)
    _, predicted = torch.max(outputs.data, 1)
    res = ''
    for i in range(img_count):
        if predicted[i] == 0:
            res += '\0'
        else:
            res += '\1'
    sock.sendto(bytes(res, 'ascii'), addr)