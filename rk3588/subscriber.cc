#include <mqtt/async_client.h>
#include <string>
#include <iostream>

const std::string SERVER_ADDRESS("mqtt://10.60.83.242:1883");
const std::string CLIENT_ID("mqtt_sub");
const std::string TOPIC("topic/test");

class callback : public virtual mqtt::callback {
    void message_arrived(mqtt::const_message_ptr msg) override {
        std::cout << "Message received: " << msg->get_payload_str() << std::endl;
    }
};

int main() {
    mqtt::async_client client(SERVER_ADDRESS, CLIENT_ID);
    callback cb;
    client.set_callback(cb);

    mqtt::connect_options connOpts;
    connOpts.set_keep_alive_interval(20);
    connOpts.set_clean_session(true);

    try {
        // Connect to EMQX broker
        client.connect(connOpts)->wait();
        std::cout << "Connected to EMQX broker" << std::endl;

        // Subscribe to topic
        client.subscribe(TOPIC, 1)->wait();
        std::cout << "Subscribed to topic: " << TOPIC << std::endl;

        // Keep running to receive messages
        std::cout << "Press Enter to exit..." << std::endl;
        std::cin.get();

        // Disconnect
        client.disconnect()->wait();
        std::cout << "Disconnected" << std::endl;
    } catch (const mqtt::exception& exc) {
        std::cerr << "Error: " << exc.what() << std::endl;
        return 1;
    }

    return 0;
}
