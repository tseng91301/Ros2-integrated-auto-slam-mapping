import rclpy 
from rclpy.node import Node 
from std_msgs.msg import String 

class simple_pub(Node): 
    def __init__(self): 
        # Define a node 
        super().__init__('ADV_leapCamp_2025_example_pub')

        # Connect to a topic
        self.publisher_ = self.create_publisher(String, 'demo_topic', 10) 

        # Create a loop to call function 
        self.timer = self.create_timer(1, self.timer_callback) 

    def timer_callback(self): 
        msg = String() 
        msg.data = 'Hello World'

        # Send a message
        self.publisher_.publish(msg) 

def main():
    rclpy.init() 
    node_publisher = simple_pub() 
    rclpy.spin(node_publisher) 
    node_publisher.destroy_node() 
    rclpy.shutdown()

if __name__ == '__main__': main()
