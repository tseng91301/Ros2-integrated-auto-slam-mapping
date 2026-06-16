# coding=UTF-8 
import rclpy 
from rclpy.node import Node 
from std_msgs.msg import String 
class simple_pub(Node): 
    def __init__(self): 
        super().__init__('simple_pub')
        self.publisher_ = self.create_publisher(String, 'chatter', 10) 
        self.timer = self.create_timer(1, self.timer_callback) 
        self.declare_parameter("my_parameter","world")
 
    def timer_callback(self): 
        msg = String() 
        msg.data = 'Hello '+ self.get_parameter('my_parameter').get_parameter_value().string_value
        self.publisher_.publish(msg) 
 
def main():
    rclpy.init() 
    node_publisher = simple_pub() 
    rclpy.spin(node_publisher) 
    node_publisher.destroy_node() 
    rclpy.shutdown()
 
if __name__ == '__main__': main()
