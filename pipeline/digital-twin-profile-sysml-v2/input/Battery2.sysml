package Battery2Twin {

    private import MetaModelDigitalTwin::*;

    #Component def PAC_Sensor { }

    #Condition def BatteryStatusStrategy {
        #strategyAction status :>> strategieActions {
            :>> name = "status";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/battery/status";
            :>> external = false;
        }
    }

    #Twin def Battery2 {
        #entity Battery2 {
            #component p16 : PAC_Sensor {
                #measureAttribute isPlugged {
                    :>> dataType default AttributeDataType::STRING;
                }
                #measureAttribute charges {
                    :>> dataType default AttributeDataType::INTEGER;
                }
                #measureAttribute consumption {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
            #constAttribute trueValue {
                :>> value default "true";
                :>> dataType default AttributeDataType::STRING;
            }
            #constAttribute maxTemp {
                :>> value default "50.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
        }

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;

        #condition operational : BatteryStatusStrategy {
            :>> leftOperand = Battery2.p16.isPlugged;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = Battery2.trueValue;
            :>> status {
                :>> feedbackTopicType = FeedbackTopicType::EXTERN;
                chargeValue :>> inputParameters = Battery2.p16.charges;
                :>> externalTopic = "Battery2/iot-data";
            }
        }
    }
}
