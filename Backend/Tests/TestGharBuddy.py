import unittest
from Backend.Models.IndianCalendar import IndianCalendar
from Backend.Models.RoutinePredictor import RoutinePredictor
from Backend.Services.DatabaseService import DatabaseService

class TestGharBuddy(unittest.TestCase):
    def testCalendarNormalDay(self):
        cal = IndianCalendar()
        cal.setSimulatedDate("06-13")
        self.assertFalse(cal.isFastingToday())
        self.assertFalse(cal.shouldSuppressCookingAlerts())
        self.assertEqual(cal.getPoojaDurationMinutes(), 20)

    def testCalendarFestivalFasting(self):
        cal = IndianCalendar()
        cal.setSimulatedDate("10-12")  # Navratri Start date
        self.assertTrue(cal.isFastingToday())
        self.assertTrue(cal.shouldSuppressCookingAlerts())
        self.assertEqual(cal.getPoojaDurationMinutes(), 40)

    def testRoutineGeyserTrigger(self):
        predictor = RoutinePredictor()
        predictor.recordEvent("toiletFlush", "active")
        prediction = predictor.predictNextAction("06:15:00")
        self.assertIsNotNone(prediction)
        self.assertEqual(prediction["predictedAction"], "turnOnGeyser")
        self.assertEqual(prediction["targetDevice"], "geyser")
        self.assertEqual(prediction["deviceCommand"], "ON")

    def testRoutineCookerWhistles(self):
        predictor = RoutinePredictor()
        predictor.recordEvent("resetCooker", 3)
        
        predictor.recordEvent("cookerWhistle", "active")
        prediction1 = predictor.predictNextAction("12:00:00")
        # Enhanced predictor returns a partial progress signal (not None) when whistleCount < targetWhistles
        # It should be a cookerCompletionAlert with low confidence (< 0.85 so it won't auto-execute)
        if prediction1 is not None:
            self.assertEqual(prediction1["predictedAction"], "cookerCompletionAlert")
            self.assertLess(prediction1["confidence"], 0.85)  # Below auto-execute threshold
        
        predictor.recordEvent("cookerWhistle", "active")
        prediction2 = predictor.predictNextAction("12:01:00")
        if prediction2 is not None:
            self.assertEqual(prediction2["predictedAction"], "cookerCompletionAlert")
        
        predictor.recordEvent("cookerWhistle", "active")
        prediction = predictor.predictNextAction("12:02:00")
        self.assertIsNotNone(prediction)
        self.assertEqual(prediction["predictedAction"], "cookerCompletionAlert")
        # At completion (3/3), confidence should be 0.98 (auto-execute)
        self.assertGreaterEqual(prediction["confidence"], 0.95)

    def testDatabaseService(self):
        db = DatabaseService()
        self.assertEqual(db.getDeviceStates()["geyser"]["status"], "OFF")
        db.updateDeviceState("geyser", "ON")
        self.assertEqual(db.getDeviceStates()["geyser"]["status"], "ON")

    def testVectorStoreSimilarity(self):
        from Backend.Services.VectorStoreService import VectorStoreService
        db = DatabaseService()
        vstore = VectorStoreService(db.pgService)
        
        # Verify rules seeded
        rules = db.pgService.getVectors()
        self.assertGreater(len(rules), 0)
        
        # Test similarity search fallback (Toilet flush matches Geyser preheating)
        similar = vstore.querySimilarRules("morning toilet flush in bathroom", topK=1)
        self.assertEqual(len(similar), 1)
        self.assertIn("geyser", similar[0]["content"].lower())

    def testAgenticPreferenceLearning(self):
        from Backend.Services.BedrockService import BedrockService
        from Backend.Services.VectorStoreService import VectorStoreService
        db = DatabaseService()
        vstore = VectorStoreService(db.pgService)
        bedrock = BedrockService()
        
        initial_count = len(db.pgService.getVectors())
        
        # Simulate user override decline
        rule = bedrock.generatePreferenceRule("turnOnGeyser", "06:15:00", "GRID")
        vstore.addRule(rule, "routine")
        
        # Verify rule is saved in the database
        updated_rules = db.pgService.getVectors()
        self.assertEqual(len(updated_rules), initial_count + 1)
        self.assertIn("geyser", updated_rules[-1]["content"].lower())

    def testEmbeddingCache(self):
        from Backend.Services.VectorStoreService import VectorStoreService
        db = DatabaseService()
        vstore = VectorStoreService(db.pgService)
        
        # Reset mock cache
        db.pgService.mockEmbeddingCache = {}
        
        # Query first time (MISS)
        v1 = vstore.getEmbedding("Pooja meditation room setup")
        # Query second time (HIT)
        v2 = vstore.getEmbedding("Pooja meditation room setup")
        
        self.assertEqual(v1, v2)
        self.assertGreater(len(db.pgService.mockEmbeddingCache), 0)

    def testOverrideConflictResolution(self):
        from Backend.Services.BedrockService import BedrockService
        from Backend.Services.VectorStoreService import VectorStoreService
        db = DatabaseService()
        vstore = VectorStoreService(db.pgService)
        bedrock = BedrockService()
        
        # Insert user override rule
        vstore.addRule("Do not automatically start the water pump motor at 07:15:00 under GRID conditions.", "override")
        
        # Build situation context matching prediction and override trigger
        context = {
            "currentTime": "07:15:00",
            "currentDate": "06-13",
            "calendarContext": {
                "isFastingDay": False,
                "festivalName": "Normal Day",
                "poojaDuration": 20
            },
            "powerGridStatus": "GRID",
            "recentSensorEvents": [{"sensorId": "waterLevelLow", "value": "active"}],
            "predictedActionDetails": {
                "predictedAction": "startWaterMotor",
                "targetDevice": "waterMotor",
                "deviceCommand": "ON",
                "confidence": 0.82,
                "reason": "Scheduled motor window reached and low water level detected."
            },
            # Retrieved similarity rules containing the matching override rule
            "ragContext": [
                {
                    "content": "Do not automatically start the water pump motor at 07:15:00 under GRID conditions.",
                    "category": "override",
                    "similarity": 0.95
                }
            ]
        }
        
        # Generate reasoning
        decision = bedrock.generateReasoning(context)
        
        # Action MUST be suppressed!
        self.assertFalse(decision["shouldExecute"])
        self.assertFalse(decision["shouldSuggest"])
        self.assertIn("suppressed", decision["actionId"])

    def testRuleConsolidation(self):
        from Backend.Services.BedrockService import BedrockService
        from Backend.Services.VectorStoreService import VectorStoreService
        db = DatabaseService()
        vstore = VectorStoreService(db.pgService)
        bedrock = BedrockService()
        
        # Setup mock db rules
        initial_rules = len(db.pgService.getVectors())
        
        # Add two highly similar/redundant rules
        vstore.addRule("Do not automatically start the water pump motor at 07:15:00 on weekdays.", "override")
        vstore.addRule("Do not automatically start the water pump motor at 07:15:00 on weekends.", "override")
        
        # Trigger consolidation
        count = vstore.consolidateRules(bedrock)
        
        # Check that at least one consolidation occurred
        self.assertGreaterEqual(count, 1)
        self.assertEqual(len(db.pgService.getVectors()), initial_rules + 1)

if __name__ == "__main__":
    unittest.main()
