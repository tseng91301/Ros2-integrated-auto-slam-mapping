import rclpy 
from rclpy.node import Node 
from std_msgs.msg import String 

class simple_sub(Node): 
    def __init__(self):
        # Define a node  
        super().__init__('ADV_leapCamp_2025_example_sub') 

        # Subscribe to a topic, and call function when message arrived
        self.subscription = self.create_subscription(String, 'demo_topic', 
         self.listener_callback, 10) 

        # Prevent ROS from posting warning of subscription unused
        self.subscription

    def listener_callback(self, msg): 
        self.get_logger().info('I heard: "%s"' % msg.data) 


def main():
    rclpy.init() 
    node_subscriber = simple_sub() 
    rclpy.spin(node_subscriber) 
    node_subscriber.destroy_node() 
    rclpy.shutdown()

if __name__ == '__main__': main()
