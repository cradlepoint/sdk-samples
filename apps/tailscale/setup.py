from download import main

PREDOWNLOAD = False # Switch to true and build to include binaries in sdk package, otherwise they will be downloaded at runtime

if __name__ == "__main__":
    if PREDOWNLOAD:
        main()