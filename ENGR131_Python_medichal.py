"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     8.3.1
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

import random
import math as m
import datetime



def main():
    seed = input("Enter random seed (integer): ")
    name = input("Enter medical device name: ")
    id = input("Enter prototype ID number: ")
    lastname = input("Enter researcher's last name: ")
    title = input("Enter researcher's title: ")

    random.seed(seed)
    nums = []
    threshold = 50

    for i in range(5):
        nums.append(random.randint(5,100))

    average = (nums[0]+nums[1]+nums[2]+nums[3]+nums[4])/5
    sqrt = m.sqrt(average)

    print("==================================================")
    print("MEDICAL DEVICE PROTOTYPE TEST REPORT")
    print("==================================================")
    print("Device Name: "+name)
    print("Prototype ID: "+id)
    print("Researcher: "+title+", "+lastname)
    print("Test Timestamp: "+datetime.datetime())


if __name__ == "__main__":
    main()
