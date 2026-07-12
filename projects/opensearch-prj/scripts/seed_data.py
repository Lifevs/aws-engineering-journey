#!/usr/bin/env python3
"""
Seeds DynamoDB with ~60 sample products spanning multiple categories.
Every write goes through DynamoDB Streams -> Indexer Lambda -> OpenSearch,
so this script IS your integration test trigger, not just fixture data.

Usage:
    pip install boto3 --break-system-packages
    TABLE_NAME=dynamo-opensearch-lab-products python3 seed_data.py
"""
import boto3
import os
import random
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

TABLE_NAME = os.environ.get("TABLE_NAME", "dynamo-opensearch-lab-products")
REGION = os.environ.get("AWS_REGION", "us-east-1")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

CATEGORIES = {
    "electronics": [
        ("Wireless Noise-Cancelling Headphones", "Over-ear bluetooth headphones with active noise cancellation and 30 hour battery life"),
        ("Mechanical Keyboard", "Hot-swappable mechanical keyboard with RGB backlighting and tactile switches"),
        ("4K Action Camera", "Waterproof action camera with image stabilization for extreme sports"),
        ("Portable SSD 1TB", "USB-C portable solid state drive with 1050MB/s read speeds"),
        ("Smart Home Hub", "Zigbee and WiFi smart home hub compatible with voice assistants"),
        ("Ultrawide Monitor", "34 inch curved ultrawide monitor with 144Hz refresh rate"),
        ("Wireless Charging Pad", "15W fast wireless charger compatible with Qi enabled devices"),
        ("Bluetooth Speaker", "Rugged portable bluetooth speaker with 360 degree sound and IPX7 rating"),
    ],
    "outdoor": [
        ("Camping Tent 4-Person", "Waterproof dome tent with easy setup for weekend camping trips"),
        ("Hiking Backpack 40L", "Lightweight hiking backpack with hydration bladder compartment"),
        ("Insulated Water Bottle", "Vacuum insulated stainless steel bottle keeps drinks cold for 24 hours"),
        ("Trekking Poles", "Adjustable aluminum trekking poles with shock absorption"),
        ("Portable Camp Stove", "Compact propane camp stove for backcountry cooking"),
        ("Sleeping Bag -10C", "Cold weather mummy sleeping bag rated for winter camping"),
        ("Headlamp Rechargeable", "USB rechargeable LED headlamp with motion sensor"),
        ("Camping Hammock", "Double camping hammock with tree straps and rain fly"),
    ],
    "home": [
        ("Ceramic Coffee Mug Set", "Set of four handmade ceramic mugs for coffee or tea"),
        ("Air Purifier HEPA", "True HEPA air purifier for rooms up to 500 square feet"),
        ("Memory Foam Pillow", "Contoured memory foam pillow for neck and shoulder support"),
        ("Cast Iron Skillet", "Pre-seasoned cast iron skillet for stovetop and oven cooking"),
        ("Robot Vacuum Cleaner", "Self-charging robot vacuum with mapping and app control"),
        ("Weighted Blanket", "15 pound weighted blanket for better sleep and relaxation"),
        ("Standing Desk Converter", "Height adjustable standing desk converter for home office"),
        ("Aromatherapy Diffuser", "Ultrasonic essential oil diffuser with color changing light"),
    ],
    "books": [
        ("Atomic Habits", "A guide to building good habits and breaking bad ones through small changes"),
        ("The Pragmatic Programmer", "Classic software engineering book on craftsmanship and best practices"),
        ("Designing Data-Intensive Applications", "Deep dive into distributed systems, databases, and data engineering"),
        ("Sapiens: A Brief History of Humankind", "A sweeping narrative of human history from evolution to modern civilization"),
        ("Deep Work", "How to cultivate focused, distraction-free work in a noisy world"),
        ("The AWS Certified Developer Guide", "Exam-focused study guide covering Lambda, DynamoDB, and serverless patterns"),
        ("Clean Architecture", "Principles for structuring maintainable and testable software systems"),
        ("The Lean Startup", "A methodology for building businesses through validated learning"),
    ],
    "fitness": [
        ("Adjustable Dumbbell Set", "Space-saving adjustable dumbbells from 5 to 50 pounds per hand"),
        ("Yoga Mat Non-Slip", "Extra thick non-slip yoga mat with alignment lines"),
        ("Resistance Bands Set", "Set of five resistance bands with varying tension levels"),
        ("Foam Roller", "High density foam roller for muscle recovery and myofascial release"),
        ("Smart Fitness Watch", "Fitness tracker with heart rate, GPS, and sleep tracking"),
        ("Jump Rope Speed", "Ball bearing speed rope for cardio and CrossFit training"),
        ("Pull-Up Bar Doorway", "No-screw doorway pull-up bar for home strength training"),
        ("Massage Gun", "Percussive therapy massage gun with six interchangeable heads"),
    ],
}

def build_items():
    items = []
    for category, products in CATEGORIES.items():
        for name, description in products:
            created = datetime.utcnow() - timedelta(days=random.randint(0, 400))
            items.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "category": category,
                "price": Decimal(str(round(random.uniform(9.99, 349.99), 2))),
                "tags": f"{category} {name.split()[0].lower()} popular",
                "createdAt": created.isoformat() + "Z",
            })
    return items

def main():
    items = build_items()
    print(f"Writing {len(items)} items to table '{TABLE_NAME}'...")
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
            time.sleep(0.05)  # gentle pacing so you can watch CloudWatch logs stream in near-real-time
    print("Done. Watch the indexer Lambda's CloudWatch log group to see stream records land.")
    print(f"Log group: /aws/lambda/{TABLE_NAME.rsplit('-products',1)[0]}-indexer")

if __name__ == "__main__":
    main()
