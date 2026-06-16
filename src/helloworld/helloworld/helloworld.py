import rclpy #import rclpy模組 
from rclpy.node import Node 

class Ex_1(Node): 
    def __init__(self): 
        super().__init__('Ex_1') #初始化 hello_python_node 
        self.get_logger().info('Hello World') #印出 Hello World 

def main():
    rclpy.init() 
    ex1 = Ex_1() 
    ex1.destroy_node() #用完記得把node清除
    rclpy.shutdown()

if __name__ == '__main__': main()
