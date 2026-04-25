from scipy.ndimage import label
from matplotlib.legend import Legend
from scipy.constants import h
import gurobipy as gp
import numpy as np
import matplotlib.pyplot as plt
import model1
import model2
import model3
from gurobipy import GRB
import pandas as pd


def main():
    modelm = gp.Model("robust")
    models = gp.Model("submodel")
    u_w_init = np.hstack((np.zeros((1,12)),np.ones((1,12))))
    u_v_init = np.hstack((np.zeros((1,12)),np.ones((1,12))))
    uin_init = {
        "uw":u_w_init,
        "uv":u_v_init
    }
   # print(f"u_w_init:{u_w_init}")
    #print(f"u_v_init:{u_v_init}")
    uout = model1.mainProblem_init(modelm,uin_init,0)
    
    print(uout)
    uin = model3.mainProblem_iterate_min(models,uout)
    residual_save = [abs(uout["LB"]-uin["UBin"])]
    while abs(uout["LB"]-uin["UBin"])>=500 :
        uout = model1.mainProblem_init(modelm,uin,0)
        residual_save.append(abs(uout["LB"]-uin["UBin"]))
        if abs(uout["LB"]-uin["UBin"])<=500:
            residual_save.append(abs(uout["LB"]-uin["UBin"]))
            print(uout)
            break
        modelsp = gp.Model()
        uin = model3.mainProblem_iterate_min(modelsp,uout)
        modelsp.dispose()
    '''
    while abs(uout["LB"]-uin["UBin"])>=100 :
        ubLast = uin["UBin"]
        o=1
        addCons = model2.mainProblemAddConstration(modelm,uin,o,uout)
        uout = addCons.rst
        uout = model1.mainProblem_init(modelm,uin,0)
        uin = model3.mainProblem_iterate_min(models,uout)

        print(f"~~~~~~~上界更新为：{uin["UBin"]}")
        o+=1
    print("_______________________________________________________________")
    '''
    #print(uout)
    
    tt = np.vstack(
        [
            uout["p_g"][0,:],  
            uout["p_g"][1,:],  
            uout["p_g"][2,:],  
            uout["p_g"][3,:],  
            uout["p_g"][4,:],  
            uout["p_buy"],
            uout["p_sell"],
            -uout["p_ch"],
            uout["p_dis"],
            uout["p_w"],
            uout["p_v"],
        ]
    )
    

    # 创建堆叠柱状图
    plt.figure(figsize=(12, 6))
    bottom = np.zeros(len(tt[0]))  # 初始化底部位置
    colors = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9364c0",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
        "#aec7e8",
    ]
     # 设置图例和标签
    legends=[
            "thermal generator1",
            "thermal generator2",
            "thermal generator3",
            "thermal generator4",
            "thermal generator5",
            "market buy",
            "market sell",
            "ESS charge",
            "ESS discharge",
            "wind power",
            "photovoltaic",
        ]

        
    #保存数据
    df = pd.DataFrame(tt,columns=range(24),index=legends)
    df.to_csv("output1.csv",index=True)
    
    for i, data in enumerate(tt):
        if (data>=0).all():
            plt.bar(
                x=range(len(data)), 
                height=data, 
                bottom=bottom, 
                color=colors[i % len(colors)],
                label=legends[i%len(legends)]
            )
            bottom += data

        if (data<=0).all():
            plt.bar(
            x=range(len(data)), 
            height=data, 
            bottom=0, 
            color=colors[i % len(colors)],
            label=legends[i%len(legends)]
            )

    plt.legend()
    plt.ylim(-200, 1800)
    plt.xlabel("T")
    plt.ylabel("Power (MW)")
    plt.title("Contribution of the Source")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    plt.figure()
    soc = uout["soc"]
    x = np.array(list(range(24)))
    plt.plot(x,soc[0],label="soc")
    plt.grid(True)

    
    plt.figure()
    residual_save = np.array(residual_save)
    plt.plot(range(len(residual_save)),residual_save,label="Residual")
    plt.grid(True)
    plt.show()
    
if __name__ == "__main__":
    main()
