---
title: capz — Free screen capture for macOS & Windows
origin: "https://capz-site.banana3339.workers.dev"
ingested: 2026-06-02
reliability: 0.7
summary: 
tags: [web]
id: SRC-20260602-5b5156d9
atoms: []
---

capz — Free screen capture for macOS & Windows

capz

ไทยEN

จับภาพหน้าจอ

บน macOS และ Windows

capz เป็นแอป native สำหรับแคปหน้าจอบน macOS และ Windows ฟรี โอเพนซอร์ส ไม่มีโฆษณา ไม่มีบัญชี

macOS ต้องตั้งค่าครั้งแรกเพื่อข้าม Gatekeeper ดูวิธีติดตั้ง

ติดตั้งบน macOSดาวน์โหลดสำหรับ Windows

ฟีเจอร์

capz ทำอะไรได้บ้าง

แคปหน้าจอ

แคปทั้งหน้าจอ พื้นที่ที่เลือก หรือหน้าต่าง พร้อมเครื่องมือแก้ไขในตัว (ลูกศร ข้อความ สติกเกอร์ เบลอ)

ฟรีและโอเพนซอร์ส

โค้ดเปิดบน GitHub ใช้ฟรีตลอด ไม่มี subscription ไม่มี telemetry

macOS และ Windows

Windows มี installer ปกติ macOS เป็น ad-hoc signed ต้องตั้งค่าครั้งแรก (ยังไม่มี Apple Developer cert)

ติดตั้ง

ติดตั้ง capz

macOSWindows

1. ติดตั้งผ่าน Homebrew

$brew install wadjakorn/capz/capz

Universal binary — รองรับทั้ง Intel และ Apple Silicon (M1/M2/M3)

2. ถ้า macOS บล็อก ให้รันคำสั่งนี้

capz ยังไม่มี Apple Developer cert (ค่าธรรมเนียมรายปี) ถูก ad-hoc signed Gatekeeper จึงบล็อกตอนเปิดครั้งแรก คำสั่งข้างล่างคือวิธีเปิดใช้งาน — ทำครั้งเดียว

$sudo xattr -dr com.apple.quarantine /Applications/capz.app

$sudo spctl --add /Applications/capz.app

$open -a capz

ถ้ายังเปิดไม่ได้ macOS 26 (Tahoe) จะมีปุ่ม Open Anyway ที่ Privacy & Security เปิดด้วย

$open /System/Library/PreferencePanes/Security.prefPane

© 2026 capz
·
ฟรี โอเพนซอร์ส

github.com/wadjakorn/capz
