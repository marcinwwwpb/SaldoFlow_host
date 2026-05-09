CC=gcc
CFLAGS=-Wall -Wextra -O2
LDFLAGS=-lcrypto
TARGET=import_watchd

all: $(TARGET)

$(TARGET): import_watchd.c
	$(CC) $(CFLAGS) -o $(TARGET) import_watchd.c $(LDFLAGS)

clean:
	rm -f $(TARGET)
