def create_sequential_file(filename, chunk_size=1024, num_chunks=3):
    """
    Creates a file with sequential chunks of 'A', 'B', and 'C'.

    Args:
        filename (str): The name of the file to create.
        chunk_size (int): The size of each chunk in bytes.
        num_chunks (int): The number of sequential chunks.
    """

    with open(filename, 'wb') as f:  # Open in binary write mode
        for i in range(num_chunks):
            if i % 3 == 0:
                chunk_data = b'A' * chunk_size  # 'A' chunk
            elif i % 3 == 1:
                chunk_data = b'B' * chunk_size  # 'B' chunk
            else:
                chunk_data = b'C' * chunk_size  # 'C' chunk

            f.write(chunk_data)

# Create a file named 'sequential_data.bin' with 1024 bytes of 'A', then 'B', then 'C'.
# create_sequential_file('sequential_data.txt')

#Create a file with 6 chunks, so that it repeats A,B,C twice.
# create_sequential_file('sequential_data_6chunks.txt', 1024, 6)

#Create a file with 12 chunks, so that it repeats A,B,C four times.
create_sequential_file('sequential_data_12chunks.txt', 1024, 1024*1024)

print("Files created successfully.")