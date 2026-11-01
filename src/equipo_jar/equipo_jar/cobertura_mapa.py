# https://github.com/ros-navigation/navigation2/issues/2283 Python example
# https://github.com/robo-friends/m-explore-ros2 m-explore-ros2
import time

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import Pose, PoseStamped, PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateThroughPoses, NavigateToPose
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessStart



import rclpy

from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSHistoryPolicy, QoSReliabilityPolicy
from rclpy.qos import QoSProfile
class CoberturaMapa(Node):
    def __init__(self, mapa):
        super().__init__(node_name='new_basic_navigator')
        self.mapa = mapa
        self.initial_pose = None
        self.last_goal = None
        self.feedback = None

        # ros2 lifecycle set /amcl activate
        self.nav_to_pose_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped,
                                                      '/initialpose',
                                                      10)

        self.possible_goals = []
        self.done = False
        self.goal_handle = None
        

    def go_to_goal(self, goal_pose):
        self.last_goal = goal_pose
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.create_pose_stamped(goal_pose)

        self.nav_to_pose_client.send_goal_async(goal_msg, self._feedbackCallback)
        send_goal_future = self.nav_to_pose_client.send_goal_async(goal_msg,
                                                                   self._feedbackCallback)
        # rclpy.spin_until_future_complete(self, send_goal_future)
        # self.goal_handle = send_goal_future.result()
        self.get_logger().info(f"Goal sent: {goal_pose}")

    
    def next_goal(self):
        if len(self.possible_goals) == 0:
            self.calculate_possible_goals()
        if not self.done:
            self.go_to_goal(self.possible_goals.pop(0))
        if len(self.possible_goals) == 0:
            self.done = True
            self.get_logger().info("All goals have been visited")
    
    def calculate_possible_goals(self):
        """
        At this moment, it only calculates the corners of the map, 
        but it can be improved to calculate more points in the map.
        """
        self.get_logger().info("Calculating possible goals")
        if self.mapa is None:
            self.get_logger().error("No map provided")
            return
        if self.done:
            self.get_logger().info("All goals have been visited")
            return
        if len(self.possible_goals) == 0:
            self.get_logger().info("Calculating possible goals")
            # Get the corners of the map
            origin_x = self.mapa.info.origin.position.x
            origin_y = self.mapa.info.origin.position.y
            width = self.mapa.info.width * self.mapa.info.resolution
            height = self.mapa.info.height * self.mapa.info.resolution
            corners = [
                self.create_pose(origin_x + width, origin_y),
                self.create_pose(origin_x, origin_y + height),
                self.create_pose(origin_x + width, origin_y + height),
                self.create_pose(origin_x, origin_y),
            ]
            self.get_logger().info(f"Possible goals calculated: {corners}")
            self.possible_goals = corners
            if self.initial_pose is None:
                self.setInitialPose(corners[-1])

    def setInitialPose(self, initial_pose):
        self.initial_pose = initial_pose
        self._setInitialPose()

    def _setInitialPose(self):
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose = self.initial_pose        
        # self.info('Publishing Initial Pose')
        self.get_logger().info(f"Initial Pose: {self.initial_pose}")
        self.initial_pose_pub.publish(msg)
        return

    def create_pose(self, x, y):
        pose = Pose()
        pose.position.x = x
        pose.position.y = y
        pose.position.z = 0.0
        pose.orientation.x = 0.0
        pose.orientation.y = 0.0
        pose.orientation.z = 0.0
        pose.orientation.w = 1.0
        return pose

    def create_pose_stamped(self, pose):
        pose_stamped = PoseStamped()
        pose_stamped.header.frame_id = 'map'
        pose_stamped.header.stamp = self.get_clock().now().to_msg()
        pose_stamped.pose = pose
        return pose_stamped

    def _feedbackCallback(self, msg):
        self.feedback = msg.feedback
        return