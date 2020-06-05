from telnetlib import Telnet
from colorama import init
from colorama import Fore, Back, Style
from itertools import compress
import re
import socket

init()
exit_program = False
change_host = 1
# git_test

while 1:
    # HOST = "15.198.21.31"
    # HOST = "15.198.17.138"
    # HOST = "15.198.17.99"
    if exit_program:
        break
    exit_program = False

    # Connect to Host System
    if change_host:
        print(Fore.LIGHTGREEN_EX, end='')
        HOST = input("\nEnter the Host IP: ")
        if HOST.startswith("http"):
            HOST = re.sub(r'https?://', '', HOST)
        if HOST.endswith('/'):
            HOST = re.sub(r'/', '', HOST)
        print(Style.RESET_ALL, end='')
    print("Connecting to Host IP: " + HOST)

    try:
        # Open Telnet connection "tn" using context manager
        with Telnet(HOST, 8, 5) as tn:
            # Read 20 Bytes from FPGA
            fpgaread = "i2c s 0x20 a 0x52 w 0x0 r 0x20\r\n"
            tn.write(fpgaread.encode("ascii"))
            eol = 'bd'
            out = tn.read_until(eol.encode("ascii"), 5)

    # Error Handling: If the compute module doesn't respond at all to Host IP provided
    # These are the errors I have encountered, just add the error type to the except arguments if you find a new one
    except (ConnectionRefusedError, socket.gaierror, socket.timeout, UnicodeError):
        print(f"{Fore.LIGHTRED_EX}Could not connect to compute module at Host IP: {HOST}{Style.RESET_ALL}")
        while 1:
            user_input = input("Type 'e' to exit, 'c' to change host IP, or 'r' or no input to rerun with same IP: ")
            if user_input == "e":
                exit_program = True
                break
            elif user_input == "c":
                change_host = 1
                break
            elif user_input == "r" or user_input == "":
                change_host = 0
                break
        continue

    # Error Handling: If Compute module iLO debugger responds but there is not Kestrel FPGA detected
    bad_response = "length 0:"
    good_response = "length 32:"
    if (out.find(bad_response.encode("ascii")) != -1) and (out.find(good_response.encode("ascii")) == -1):
        print(f"{Fore.LIGHTRED_EX}Compute module found, but Kestrel FPGA did not respond, "
              f"please enter another Host IP or try again{Style.RESET_ALL}")
        user_input = input("Type 'e' to exit, 'c' to change host IP, or 'r' or no input to rerun with same IP: ")
        while 1:
            if user_input == "e":
                exit_program = True
                break
            elif user_input == "c":
                change_host = 1
                break
            elif user_input == "r" or user_input == "":
                change_host = 0
                break
        continue

    # Parse the first 16 Bytes of the response from FPGA
    fpga_line1_binary = out[(out.find(good_response.encode("ascii")) + 13):(out.find(good_response.encode("ascii")) + 60)]
    # Parse the second 16 Bytes of the response from FPGA
    fpga_line2_binary = out[(out.find(good_response.encode("ascii")) + 68):-2]
    # Convert FPGA read from binary to ascii
    fpga_line1 = fpga_line1_binary.decode("ascii")
    fpga_line2 = fpga_line2_binary.decode("ascii")
    # Load raw data into FPGA address accessible list
    fpga_bytes = fpga_line1.split() + fpga_line2.split()

    print(f"\nRaw FPGA output:\n\t{fpga_line1}\n\t{fpga_line2}\n")

    ############################
    # Raw Assignments
    ############################

    fpga_version = fpga_bytes[0].upper()
    core_version = fpga_bytes[1].upper()
    expansion_type = fpga_bytes[2][0].upper()  # addressing to the upper nibble
    PCA_revision = fpga_bytes[2][1].upper()  # addressing to the lower nibble
    slot_presence_byte4 = fpga_bytes[4].upper()
    slot_presence_byte5 = fpga_bytes[5].upper()
    first_fail = fpga_bytes[12].upper()
    sequence_fault_raw = fpga_bytes[12].upper()
    pgood1 = fpga_bytes[14].upper()
    pgood2 = fpga_bytes[15].upper()
    misc_fault_raw = fpga_bytes[16].upper()
    mezz5 = fpga_bytes[17].upper()
    riser_type = fpga_bytes[18].upper()
    switch_config = fpga_bytes[24].upper()

    ############################
    # Byte Parsing
    ############################

    # Byte 0x2
    expansion_type_parsed = "Error: Unknown Expansion Type"
    if expansion_type == "1":
        expansion_type_parsed = "Kestrel-H"
    elif expansion_type == "2":
        expansion_type_parsed = "Kestrel-E2"
    elif expansion_type == "3":
        expansion_type_parsed = "Kestrel-E4"

    # Byte 0x4 and 0x5
    slots = [False, False, False, False, False, False, False, False]
    kestrel_e_slots = ['4', '5', '6', '7', '', '', '', '']
    kestrel_h_slots = ['6', '7', '8', '9', '10', '11', '12', '13']
    slot4_int = int(slot_presence_byte4, 16)
    slot5_int = int(slot_presence_byte5, 16)
    slots[0] = True if slot4_int & 1 else False
    slots[2] = True if slot4_int & 2 else False
    slots[4] = True if slot4_int & 4 else False
    slots[6] = True if slot4_int & 8 else False
    slots[1] = True if slot5_int & 1 else False
    slots[3] = True if slot5_int & 2 else False
    slots[5] = True if slot5_int & 4 else False
    slots[7] = True if slot5_int & 8 else False

    # Join allows us to comma separate our list of slots
    # List/Compress iterates over our boolean 'slots' and maps it to the above kestrel slot definitions

    # Kestrel-H PCIe Slot Numbering - Starting at 6
    if expansion_type == "1":
        all_slots = ', '.join(list(compress(kestrel_h_slots, slots)))
    # Kestrel-E2 PCIe Slot Numbering - Starting at 4
    elif expansion_type == "2":
        all_slots = ', '.join(list(compress(kestrel_e_slots, slots)))
    # Kestrel-E4 PCIe Slot Numbering - Starting at 4
    elif expansion_type == "3":
        all_slots = ', '.join(list(compress(kestrel_e_slots, slots)))
    else:
        all_slots = "Unknown Expander Type"

    # Byte 0xC
    first_fail_id = int(first_fail, 16) & 15
    first_fail_transorb = int(first_fail, 16) & 16
    first_fail_overtemp = int(first_fail, 16) & 32
    first_fail_pgd = int(first_fail, 16) & 64
    first_fail_efuse = int(first_fail, 16) & 128

    # Byte 0xD
    sequence_fault = [False, False, False, False, False, False, False, False]
    sequence_fault_names = ["PGD_MAIN_EFUSE", "PGD_P3V3_CTRL", "PGD_P5V_GATE_CTRL", "PGD_V3P3", "PGD_P1V_VDDIO",
                            "PGD_P0V082_AVD_PCIE", "PGD_V0P82", "PGD_P1V8"]
    sequence_fault_int = int(sequence_fault_raw, 16)
    sequence_fault[0] = True if sequence_fault_int & 1 else False
    sequence_fault[1] = True if sequence_fault_int & 2 else False
    sequence_fault[2] = True if sequence_fault_int & 4 else False
    sequence_fault[3] = True if sequence_fault_int & 8 else False
    sequence_fault[4] = True if sequence_fault_int & 16 else False
    sequence_fault[5] = True if sequence_fault_int & 32 else False
    sequence_fault[6] = True if sequence_fault_int & 64 else False
    sequence_fault[7] = True if sequence_fault_int & 128 else False

    # Byte 0xE
    pgood = [False, False, False, False, False, False, False, False, False]
    pgood_names = ["PGD_P2V5_STBY_BANK3", "PGD_MAIN_EFUSE", "PGD_P3V3_CTRL", "PGD_P5V_GATE_CTRL", "PGD_V0P82",
                   "PGD_P0V082_AVD_PCIE", "PGD_P1V_VDDIO", "PGD_V3P3", "PGD_P1V8"]
    pgood1_int = int(pgood1, 16)
    pgood2_int = int(pgood2, 16)
    pgood[0] = True if pgood2_int & 128 else False
    pgood[1] = True if pgood1_int & 1 else False
    pgood[2] = True if pgood1_int & 2 else False
    pgood[3] = True if pgood1_int & 4 else False
    pgood[4] = True if pgood1_int & 8 else False
    pgood[5] = True if pgood1_int & 16 else False
    pgood[6] = True if pgood1_int & 32 else False
    pgood[7] = True if pgood1_int & 64 else False
    pgood[8] = True if pgood1_int & 128 else False

    # Byte 0x10

    misc_fault = [False, False, False, False, False, False, False, False]
    misc_fault_names = ["EMC1464_THERM", "POWER BRAKE ASSERTED", "Unknown", "Unknown", "VR_FAULT_P0V82",
                        "VR_HOT_P0V82", "VR_FAULT_P3V3", "VR_HOT_P3V3"]
    misc_fault_int = int(misc_fault_raw, 16)
    misc_fault[0] = True if misc_fault_int & 1 else False
    misc_fault[1] = True if misc_fault_int & 2 else False
    misc_fault[2] = True if misc_fault_int & 4 else False
    misc_fault[3] = True if misc_fault_int & 8 else False
    misc_fault[4] = True if misc_fault_int & 16 else False
    misc_fault[5] = True if misc_fault_int & 32 else False
    misc_fault[6] = True if misc_fault_int & 64 else False
    misc_fault[7] = True if misc_fault_int & 128 else False

    # Byte 0x12
    riser_type_list = ["Kestrel-H Dual x8", "Kestrel-E2 Single x16", "Kestrel-E4 Dual x8", "Empty"]
    riser_type1 = int(riser_type, 16) & 3
    riser_type2 = (int(riser_type, 16) & 12) >> 2
    riser_type3 = (int(riser_type, 16) & 48) >> 4
    riser_type4 = (int(riser_type, 16) & 192) >> 6

    # Byte 0x17
    mezz5_therm = (int(mezz5[0], 16) & 8) >> 3  # extracting individual bits from this byte
    mezz5_p12v_shrt = (int(mezz5[0], 16) & 4) >> 2
    mezz5_prsnt = int(mezz5[0], 16) & 1
    mezz5_pgd_vmain = (int(mezz5[1], 16) & 8) >> 3
    mezz5_pgd_vaux = (int(mezz5[1], 16) & 4) >> 2
    mezz5_vmain_en = (int(mezz5[1], 16) & 2) >> 1
    mezz5_vaux_en = int(mezz5[1], 16) & 1

    #######################################################
    # Display ----- using colorama module for color
    #######################################################
    print(f"{Fore.LIGHTGREEN_EX}FPGA Version: \t\t\t0x{fpga_version} {Style.RESET_ALL}")
    print(f"Core Version: \t\t\t0x{core_version}")
    print(f"{Fore.LIGHTMAGENTA_EX}Expansion Type: \t\t {expansion_type_parsed}{Style.RESET_ALL}")
    print(f"PCA revision: \t\t\t0x{PCA_revision}")

    print(f"{Fore.LIGHTCYAN_EX}Populated PCIe Slots:\t\t{all_slots}{Style.RESET_ALL}")  # Reset Default Text

    print(f"Switched Power/PGood1: \t\t0x{pgood1}\t\t\t(If ON, non 0xFF is bad, if OFF, 0x00 is expected)")
    print(f"STBY Power/PGood2: \t\t0x{pgood2}\t\t\t(Anything non 0xFF is bad)")
    print(f"First Fail:\t\t\t0x{first_fail}")

    print(Fore.LIGHTRED_EX, end='')
    if first_fail_efuse != 0:
        print("Failure Detected - eFuse Fault")
    if first_fail_pgd != 0:
        print("Failure Detected - PGD Fault - PGD Removed from Expander")
    if first_fail_overtemp != 0:
        print("Failure Detected - Overtemperature Fault")
    if first_fail_transorb != 0:
        print("Failure Detected - Transorb Fault")
    if first_fail_id != 0:
        print(f"Failure Detected - Fail ID:\t{first_fail_id}")
        for i in range(len(sequence_fault)):
            if sequence_fault[i]:
                print(f"Failed Voltage Rail:\t\t{sequence_fault_names[i]}")
                break
    print(Style.RESET_ALL, end='')

    for i in range(len(misc_fault)):
        if misc_fault[i]:
            print(f"{Fore.LIGHTRED_EX}MISC Fault Found:\t\t{misc_fault_names[i]}{Style.RESET_ALL}")
            break

    print(f"Riser1 Type:\t\t\t{riser_type_list[riser_type1]}")
    print(f"Riser2 Type:\t\t\t{riser_type_list[riser_type2]}")
    if expansion_type == "1":
        print(f"Riser3 Type:\t\t\t{riser_type_list[riser_type3]}")
        print(f"Riser4 Type:\t\t\t{riser_type_list[riser_type4]}")

    print(f"{Fore.LIGHTYELLOW_EX}Switch Config Selection:\t0x{switch_config}{Style.RESET_ALL}")

    if mezz5_prsnt == 1:
        print("Mezzanine 5 Detected")
        print(f"\tMezz5_THERM: \t\t\t{mezz5_therm}")
        print(f"\tMezz5_P12V_SHRT: \t\t{mezz5_p12v_shrt}")
        print(f"\tMezz5_PGD_VMAIN: \t\t{mezz5_pgd_vmain}")
        if mezz5_pgd_vmain == 0 and mezz5_vmain_en == 1:
            print(f"{Fore.LIGHTRED_EX}\t Mezz VMAIN Fault Detected{Style.RESET_ALL}")
        print(f"\tMezz5_PGD_VAUX: \t\t{mezz5_pgd_vaux}")
        if mezz5_pgd_vaux == 0 and mezz5_vaux_en == 1:
            print(f"{Fore.LIGHTRED_EX}\t Mezz VAUX Fault Detected{Style.RESET_ALL}")
        print(f"\tMezz5_VMAIN_EN: \t\t{mezz5_vmain_en}")
        print(f"\tMezz5_VAUX_EN: \t\t\t{mezz5_vaux_en}")

    while 1:
        user_input = input("Type 'e' to exit, 'c' to change host IP, or 'r' or no input to rerun with same IP: ")
        if user_input == "e":
            exit_program = True
            break
        elif user_input == "c":
            change_host = 1
            break
        elif user_input == "r" or user_input == "":
            change_host = 0
            break
    if exit_program:
        break
