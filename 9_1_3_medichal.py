"""
Course Number: ENGR 13100

Description:
    Replace this line with a description of your program.

Assignment Information:
    Assignment:     9.1.3
    Author:         Saharsh Medichalam, medichal@purdue.edu
    Section:        115
    Team:           28

"""

""" Write any import statements here (and delete this line)."""


def main():
    voltage = float(input("Enter voltage (V): "))
    resistance = float(input("Enter resistance (ohms): "))

    power = calc_power(voltage, resistance)

    print("Calculated power: "+str(round(power, 2))+" W")


def calc_power(v, r):
    p = v**2/r
    return p


if __name__ == "__main__":
    main()



