# Copyright 2022 The Bazel Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script to release rules_java."""

import argparse
import sys
import subprocess
import re

def git(*args):
  """Runs git as a subprocess, and returns its stdout as a list of lines."""
  return subprocess.check_output(["git"] +
                                 list(args)).decode("utf-8").strip().split("\n")

def read_file(filename):
  with open(filename, 'r') as f:
    content = f.read()    
  return content

def get_sha_breakdown(input):
	artifacts = {}
	input = input.split("\n")
	names = ["java_tools_linux", "java_tools_windows", "java_tools_darwin_x86_64", "java_tools_darwin_arm64", "java_tools"]
	i = 0
	for artifact in input:
		dict = {}
		dict["path"] = input[i].split()[0]
		dict["sha"] = input[i].split()[1]
		artifacts[names[i]] = dict
		i += 1
	return artifacts

def get_version(artifacts):
  path = artifacts["java_tools"]["path"]
  version = path[path.find("/v"):path.find("/java_")][1:]
  return version

def is_rc(artifacts):
  path = artifacts["java_tools"]["path"]
  if path.find("-rc") == -1: 
    return False
  return True

def get_block(name):
  data = read_file("repositories.bzl")
  end = False
  lines = data.split("\n")
  counter = 0
  string = "\"remote_" + name + "\""
  for line in lines:
    counter += 1
    if "maybe(" in line:
      block_start = line
      block_start_line = counter
    if string in line:
      end = True
    if end == True:
      if ")" in line:
        block_end = line
        block_end_line = counter
        break
  return block_start_line, block_end_line

def get_replacement(line, artifacts, item):
  # Replace sha
  sha_replacement = re.search("sha256 = \"(.+?)\",", line).group(1)
  line = line.replace(sha_replacement, artifacts[item]["sha"]) 
  
  # Replace urls
  url = url_replacement = re.search("urls = \[(\n.*)*\],", line).group(0)
  if is_rc(artifacts):
    # Remove GitHub url if it exists
    try:
      github_url = re.search("(\n.*)\"https://github.com(.*)\",", url_replacement).group(0)
      url_replacement = url_replacement.replace(github_url, "")
    except:
      pass
  else:
    # Add GitHub url
    existing_url = re.search("(\n.*)\"https://mirror.bazel.build(.*)\",", url_replacement).group(0)
    indent = re.search("( *)", existing_url.strip("\n")).group(1)
    version = get_version(artifacts)
    github_url = "\n" + indent + "\"https://github.com/bazelbuild/java_tools/releases/download/java_" + version + "/" + item + "-" + version + ".zip\","
    url_replacement = url_replacement.replace(existing_url, existing_url + github_url)

  # Update mirror url
  mirror_url = re.search("release(.*)\.zip", url_replacement).group(0)
  url_replacement = url_replacement.replace(mirror_url, artifacts[item]["path"])
  line = line.replace(url, url_replacement)
  return line

def update_file(start, end, artifacts, item):
  with open('repositories.bzl', 'r+') as f:
    line = ''.join(f.readlines()[start:end-1])
    f.seek(0)
    file_contents = f.read().replace(line, get_replacement(line, artifacts, item))
    f.seek(0)
    f.write(file_contents)
    f.truncate()  

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument(
      '--artifacts',
      required=True,
      dest='artifacts',
      help='Output from create_java_tools_release.sh')
  parser.add_argument(
      '--token',
      required=True,
      dest='token',
      help='GitHub token for bazel-io')
  opts = parser.parse_args()

  print("opts.artifacts = ", opts.artifacts)	

  artifacts = get_sha_breakdown(opts.artifacts)
  github_token = opts.token

  print("+++ Creating a new branch")
  git("remote", "set-url", "origin", "https://bazel-io:" + github_token + "@github.com/bazelbuild/rules_java.git")
  # branch_name="java_tools-" + get_version(artifacts)
  branch_name = "keertk-testing"
  try:
    git("checkout", "-b", f"{branch_name}")
  except:
    git("checkout", f"{branch_name}")  

  print("+++ Updating repositories.bzl")
  for item in artifacts:
    start_line, end_line = get_block(item)
    update_file(start_line, end_line, artifacts, item)

  print("+++ Commiting updates")
  git("config", "--global", "user.name", "bazel-io")
  git("config", "--global", "user.email", "bazel-io@google.com")  
  git("add", ".")
  git("commit", "-a", "-m", "\"Update java_tools \"")
  git("push", "--set-upstream", "origin", f"{branch_name}")

if __name__ == '__main__':
  main()
