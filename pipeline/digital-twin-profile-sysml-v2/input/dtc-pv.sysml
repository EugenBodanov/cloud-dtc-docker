package dtcpv {
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

    #Twin def dtcpv {
        #entity dtcpv {
            #component sensor : PV_Sensor {
                #measureAttribute generatedPower {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
        }
        

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;

        #condition isGenerating : PVProductionStrategy {
            :>> leftOperand = dtcpv.sensor.generatedPower;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = dtcpv.sensor.generatedPower;
            :>> production {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                generatedPower :>> inputParameters = dtcpv.sensor.generatedPower;
            }
        }
    }
}
