package MGrid {

    private import MetaModelDigitalTwin::*;

    #Component def PAC_Sensor {
        
    }
    #Entity def Battery{
        #component sensor: PAC_Sensor{
            #measureAttribute totalCapacity {
                    :>> dataType default AttributeDataType::INTEGER;
                }
        }
        
    }

    #Entity def PV{
        #component sensor: PAC_Sensor{
            #measureAttribute output{
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
        
    }

    #Condition def StopCharging{
        #strategyAction stopCharging :>>strategieActions{
        :>> name = "StopCharging";
        :>> strategyType = StrategyType::LAMBDA;
        :>> pathToCode = "/home/marcocotrotzo/PycharmProjects/SymlCOnv/DigitalTwinProfileSysMLv2/testLambdaFunctions/high-temperature-callback";
        :>> external = false;
       
    }

    #Entity def Charger{
        #constAttribute maxConsumption {
            :>> value default "50.0";
            :>>dataType default AttributeDataType::DOUBLE;
        }
        #component sensor: PAC_Sensor;
    }

     

    #Twin def MGrid {

        #entity MicroGrid{
            #entity battery : Battery{

                p16:>>sensor;
            }
            #entity KebaP30 : Charger{
                :>>maxConsumption {
                    :>> value default "15.0";
                }
                p13 :>> sensor{
                    #measureAttribute power {
                    :>> dataType default AttributeDataType::DOUBLE;
                    }
                }
            }
            #entity SieVersicharge :Charger{

                p14 :>> sensor{
                    #measureAttribute consumption {
                    :>> dataType default AttributeDataType::DOUBLE;
                    }
                }
            }
            #entity SieChargeCC: Charger{
                p12 :>> sensor{
                    #measureAttribute consumption {
                    :>> dataType default AttributeDataType::DOUBLE;
                    }
                }
            }
            #entity pv : PV{
                pV1 :>> sensor;
            }
            #entity SieChargeD : Charger{
                p17 :>> sensor{
                    #measureAttribute consumption {
                    :>> dataType default AttributeDataType::DOUBLE;
                    }
                }
            }
            #entity SieCPC20 : Charger{
                p11 :>> sensor{
                    #measureAttribute consumption {
                    :>> dataType default AttributeDataType::DOUBLE;
                    }
                }
            }
    }
        :>>hotDatabaseRetentionDays default 30;
        :>>coldDatabaseRetentionDays default 30;

        #condition stopCharging :StopCharging{
            :>>leftOperand = MicroGrid.KebaP30.p13.power;
            :>>operator = ComparisonOperator::EQUAL;
            :>>rightOperand = MicroGrid.KebaP30.maxConsumption;
            :>>stopCharging{
                :>> feedbackTopicType = FeedbackTopicType::INTERN;
                :>> componentTopic = MicroGrid.KebaP30.p13;
            }
        }
        #condition stopChargingP14:StopCharging{
            :>>leftOperand = MicroGrid.SieVersicharge.p14.consumption;
            :>>operator = ComparisonOperator::EQUAL;
            :>>rightOperand = MicroGrid.SieVersicharge.maxConsumption;
            stopCharging14:>>stopCharging{
                :>> feedbackTopicType = FeedbackTopicType::EXTERN;
                :>> externalTopic = "EXTERN_TPIC";
                :>> customPayload = "{\"message\":\"High Consumption Alert\"}";
                test1 :>> inputParameters = MicroGrid.SieVersicharge.p14.consumption;
                test2 :>> inputParameters = MicroGrid.SieVersicharge.maxConsumption;
                test3 :>> outputParameters = AttributeDataType::STRING;
                test6 :>> outputParameters = AttributeDataType::DOUBLE;
                :>>outputParameters = AttributeDataType::DOUBLE;
                test7 :>> inputParameters = MicroGrid.SieVersicharge.maxConsumption;
                
        }
            }
        }
    
    }
}