# coding=UTF-8 
import rclpy 
from rclpy.node import Node 
from std_msgs.msg import String 

class simple_sub(Node): 
    def __init__(self): 
        super().__init__('simple_sub') 

        #訂閱，需要指定頻道chatter和收到訊息由哪個方法處理訊息（listener_callback）
        self.subscription = self.create_subscription(String,'chatter',self.listener_callback,10) 
        self.subscription #防止ROS跳出訂閱後未使用的警告

    def listener_callback(self, msg): 
        self.get_logger().info('I heard: "%s"' % msg.data) 

def main():
    rclpy.init() 
    node_subscriber = simple_sub() 
    rclpy.spin(node_subscriber) 
    node_subscriber.destroy_node() 
    rclpy.shutdown()

if __name__ == '__main__': main()

