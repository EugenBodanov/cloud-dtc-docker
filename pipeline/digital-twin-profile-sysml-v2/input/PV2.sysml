package PV2Twin {
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

    #Twin def PV2 {
        #entity PV2 {
            #constAttribute generatedPower {
                :>> value default "50.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
        }

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;

        #condition isGenerating : PVProductionStrategy {
            :>> leftOperand = PV2.generatedPower;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = PV2.generatedPower;
            :>> production {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                generatedPower :>> inputParameters = PV2.generatedPower;
            }
        }
    }
}
