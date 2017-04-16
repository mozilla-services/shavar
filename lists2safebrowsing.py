#!/usr/bin/python

import sys
import os
import time

def main():
  if len(sys.argv) < 3:
    sys.exit("Usage: " + sys.argv[0] + " <input_directory> <output_file>")

  # initial chunk number, each handler will produce at least one separate
  # chunk (one chunk per list it processes) and each chunk must have a
  # unique chunk number. for now the initial chunk number is the epoch
  chunkInit = time.time();
  chunk = chunkInit;

  # output file,
  # representation of extracted URLs in safebrowsing-list format
  f_out = open(sys.argv[2], "wb")

  # output file,
  # debug version of f_out. binary hashes are now in hex format
  # and they are followed by a LF
  f_dbg = open(sys.argv[2] + ".dbg", "w");

  # log file
  f_log = open(sys.argv[2] + ".log", "w");

  # try to load handler for root directory itself
  try:
    print "[+] Processing", os.path.split(sys.argv[1])[1];
    mod = __import__('handler_' + os.path.split(sys.argv[1])[1]);
    chunk = mod.main(sys.argv[1], f_out, f_dbg, f_log, chunk);
  # or try to find handlers in the root's children
  except ImportError:
    # non recursive listing
    for name in os.listdir(sys.argv[1]):
      # consider directories (and links to directories)
      if os.path.isdir(os.path.join(sys.argv[1], name)):
        # ignore names beginnig with a dot
        if name.find(".") == 0:
          print "[-] Ignoring", os.path.join(sys.argv[1], name);
          continue
        # Use directory names to load corresponding handlers
        try:
          print "[+] Processing", os.path.join(sys.argv[1], name);
          mod = __import__('handler_' + name);
          chunk = \
            mod.main(os.path.join(sys.argv[1], name),
              f_out, f_dbg, f_log, chunk);
        except ImportError:
          print "[!] No handler found for", name
          pass;
      # ignore everything else
      else:
        print "[-] Ignoring", os.path.join(sys.argv[1], name);

  f_out.close();
  f_dbg.close();
  f_log.close();

  print "[+] Produced", (chunk - chunkInit), "chunks"


if __name__ == "__main__":
  main()
