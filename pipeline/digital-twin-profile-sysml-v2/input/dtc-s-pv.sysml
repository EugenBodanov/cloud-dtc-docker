package dtcspv {
    private import MetaModelDigitalTwin::*;

    #Component def PV_Sensor { }

    #Condition def PVProductionStrategy {
        #strategyAction production :>> strategieActions {
            :>> name = "production";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/pv/production";
            :>> external = false;
        }
    }

    #Condition def PVToBatteryPushStrategy {
        #strategyAction pvToBatteryPush :>> strategieActions {
            :>> name = "pv-to-battery-push";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/pv/pv-to-battery-push";
            :>> external = false;
        }
    }

    #Twin def dtcspv {
        #entity dtcspv {
            #component sensor : PV_Sensor {
                #measureAttribute generatedPower {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
        }


        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;

        #condition isGenerating : PVProductionStrategy {
            :>> leftOperand = dtcspv.sensor.generatedPower;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = dtcspv.sensor.generatedPower;
            :>> production {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                generatedPower :>> inputParameters = dtcspv.sensor.generatedPower;
            }
        }

        #condition pushToBattery : PVToBatteryPushStrategy {
            :>> leftOperand = dtcspv.sensor.generatedPower;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = dtcspv.sensor.generatedPower;
            :>> pvToBatteryPush {
                :>> feedbackTopicType = FeedbackTopicType::EXTERN;
                generatedPower :>> inputParameters = dtcspv.sensor.generatedPower;
                :>> externalTopic = "dtcsbat/iot-data";
            }
        }
    }
}
