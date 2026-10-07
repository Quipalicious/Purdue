"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     10.1.2
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

""" Write any import statements here (and delete this line)."""


def main():
    num = int(input("Enter a number: "))

    while num != 0:
        print("You entered: "+str(num))
        num = int(input("Enter a number: "))
    print("Done!")

if __name__ == "__main__":
    main()
