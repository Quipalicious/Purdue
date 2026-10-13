"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     10.1.3
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28 

"""

""" Write any import statements here (and delete this line)."""


def main():
    char = input("Enter a character: ")
    string = "" + char

    for i in range(10):
        print(string)
        string += char
            


if __name__ == "__main__":
    main()
