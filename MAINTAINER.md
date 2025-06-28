# Publish a new version of the python package

If code coverged towards a new version (e.g. fixing some problems or implementing new features), define the new version in `setup.py` and create a new commit.

Go to `Tags` > `Releases` and create a new release using the tag and title `v"new.versions.number"`.

The new package version will be published to pip by running a GitHub Actions deployment automatically.
