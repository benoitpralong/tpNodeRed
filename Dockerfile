FROM nodered/node-red:4.1

RUN npm config set strict-ssl false
# Installation des plugins Node-RED

RUN npm install \
    node-red-dashboard \
    node-red-contrib-opcua \
    #node-red-contrib-opcua-server \
    node-red-contrib-aedes \
    node-red-contrib-postgresql \
    node-red-contrib-kafkajs \
    --save
