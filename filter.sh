#!/bin/bash
grep Memory *.txt -n | grep -vi delete | grep -vi free |grep -v "include"