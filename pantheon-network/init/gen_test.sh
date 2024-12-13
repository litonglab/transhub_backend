#!/bin/sh
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <project_directory> <user_data_directory>"
    exit 1
fi


# 从外部参数接收目录路径
PROJECT_DIR=$1
USER_COMP_DIR=$2
TARGET_DIR=$(dirname "$USER_COMP_DIR") # 获取目录的父目录 

  if [ -d "$USER_COMP_DIR" ]; then
    echo "Setting up build in directory: $USER_COMP_DIR"
    cp $PROJECT_DIR $TARGET_DIR -r
    
    cd "$USER_COMP_DIR" 
    
    # 创建软链接
    # ln -s "$PROJECT_DIR/autogen.sh" autogen.sh
    # ln -s "$PROJECT_DIR/configure.ac" configure.ac
    # ln -s "$PROJECT_DIR/Makefile.am" Makefile.am
    # ln -s "$PROJECT_DIR/src" src
    # ln -s "$PROJECT_DIR/datagrump" datagrump
    # ln -s "$PROJECT_DIR/examples" examples
    # ln -s "$PROJECT_DIR/config.h.in" config.h.in
    
    # 运行构建命令
    ./autogen.sh
    ./configure
    make
    
    echo "Build completed for $USER_COMP_DIR"
  else
    echo "Directory $USER_COMP_DIR does not exist. Skipping..."
  fi
