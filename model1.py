from pyexpat import model
import gurobipy as gp
import numpy as np
from gurobipy import GRB, quicksum
'''
主问题的优化变量为x和y，固定的优化变量为u,每次子问题都会更新与u有关的约束
'''
def mainProblem_init(model1:gp.Model,uin:dict,o):
  print(f"内层场景：~~~~~{uin}")
  '''
  已知参数
  '''
  alpha = 0.9
  w_l = np.array([0.9, 1, 1.1])
  pw_f = np.array(
    [680,720,850,600,750,800,780,700,650,580,500,450,400,380,420,550,620,750,820,900,950,880,800,760]
                  ).reshape(1,24)
  pv_f = np.array(
          [0,0,0,0,0,0,50,180,350,520,680,690,800,780,650,480,280,100,20,0,0,0,0,0]
                ).reshape(1,24)
  pload =np.array(
          [850,780,750,760,820,900,1050 ,1180,1250,1200,980,920,880,860,900,950,1020,1150,1280,1320,1300,1200,1100,950]
                  )#双峰负荷曲线
  p_g_min = 0.25*np.array([200, 200, 150, 120, 70])
  p_g_max = 0.25*np.array([460, 400, 350, 300, 150])
  '''
  交易
  '''
  p_m_max = 800
  remp_u_d = 0.25*np.array([240, 210, 150, 120, 70])  # >=pgmin
  t_on_and_off = np.array([3, 3, 3, 3, 3])
  a = 1e-5 * np.array([1.02, 1.21, 2.17, 3.42, 6.63])
  b = np.array([0.277, 0.288, 0.29, 0.292, 0.306])
  c = np.array([9.2, 8.8, 7.2, 5.2, 3.5])
  sit = np.array([25.6, 22.3, 16.2, 12.3, 4.6])
  e = np.array([0.877, 0.877, 0.877, 0.877, 0.979])
  lamda = np.array([0.94, 0.94, 0.94, 0.94, 1.03])
  # 储能模型中的常量
  capmax =800
  p_s_max =200
  p_s_min= 0
  socmax = 0.9#储能电量百分比
  socmin = 0.2
  theta = 0.01
  yita = 0.95
  kees = 0.009
  # 碳交易
  #二次碳惩罚因子50块

  #碳排放因子,依次为火电，电网，碳排放因子数据来自
  #国家温室气体排放因子数据库：https://data.ncsc.org.cn/factories/index
  efc_max =400
  coef = np.array([0.72,0.5306])
  #___________
  # 循环控制变量
  # 时间
  T = 24
  # 火力发电机组数
  n_g = 5

  '''
  约束规划
  '''
  if o==0:

    #火电变量
    p_g = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name="火电出力")
    p_g_2 = model1.addMVar((n_g,T),vtype=GRB.CONTINUOUS,name = "火电出力的平方线性化")
    u_g = model1.addMVar((n_g,T),vtype= GRB.BINARY,name="火电启停状态")
    u_start = model1.addMVar((n_g,T),vtype= GRB.BINARY,name="火电启动时刻")
    u_stop = model1.addMVar((n_g,T),vtype=GRB.BINARY,name ="火电机组停止时刻")
    #火电约束

    model1.addConstrs((p_g[i,j]<=u_g[i,j]*p_g_max[i] for i in range(n_g) for j in range(T)))
    model1.addConstrs((p_g[i,j]>=u_g[i,j]*p_g_min[i] for i in range(n_g) for j in range(T)))
    for i in range(n_g):
      for t in range(T):
        if(t==0):
          model1.addConstr(p_g[i,t]<=remp_u_d[i])#初值设为0
        else:  
          model1.addConstr(p_g[i,t]-p_g[i,t-1]<=remp_u_d[i])
          model1.addConstr(p_g[i,t-1]-p_g[i,t]<=remp_u_d[i])
    for i in range(n_g):
      for t in range(T):
        if t==0:
          model1.addConstr(u_start[i,t]-u_stop[i,t] == u_g[i,t])
        else:
          model1.addConstr(u_start[i,t]-u_stop[i,t] == u_g[i,t]-u_g[i,t-1])
        model1.addConstr(u_start[i,t] + u_stop[i,t] <=1)
        for k in range(t_on_and_off[i]):
          model1.addConstr(u_start[i,t]<=u_g[i,min(t+k,T-1)])
          model1.addConstr(u_stop[i,t]<=1-u_g[i,min(t+k,T-1)])
    #火电成本
    #线性化二次项
    lxpg2=np.array([np.linspace(start =0,stop=p_g_max[i],num=11) for i in range(n_g)])
    lypg2 = lxpg2**2
    for n in range(n_g):
      for t in range(T):
        model1.addGenConstrPWL(p_g[n, t].item(), p_g_2[n, t].item(), lxpg2[n],lypg2[n])
    c_g = 0
    c_u = 0
    for i in range(n_g):
      for t in range(T):
        c_gi = a[i]*p_g_2[i,t]+ b[i]*p_g[i,t]+ c[i]
        c_u =c_u+ sit[i]*(u_start[i,t]+u_stop[i,t])
        c_g +=c_gi
    
    #电市场交易：
    #变量：
    p_buy = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,name = "电交易出力")
    p_sell = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,name = "电交易出力")
    u_buy = model1.addMVar((1,T),vtype=GRB.BINARY,name = "电交易出力")
    u_sell = model1.addMVar((1,T),vtype=GRB.BINARY,name = "电交易出力")
    #联络线约束
    model1.addConstr(-p_buy<=0)
    model1.addConstr(p_buy<=p_m_max*u_buy)
    model1.addConstr(-p_sell<=0)
    model1.addConstr(p_sell<=p_m_max*u_sell)
    model1.addConstr(u_sell+u_buy<=1)
    

    # 成本：
    c_m=0
    for t in range(T):
      c_m +=50*p_buy[0,t]+10*p_sell[0,t]
    #储能：
    soc_init = 0.5
    # 变量：
    soc = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = socmin,ub = socmax,name = "电量百分比")
    p_ch = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能充电功率")
    p_dis = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb=0,name="储能放电功率")
    u_ch = model1.addMVar((1,T),vtype=GRB.BINARY,name = "储能充电状态")
    u_dis = model1.addMVar((1,T),vtype=GRB.BINARY,name = "储能放电状态")
  #约束：
    model1.addConstr(p_ch<=p_s_max*u_ch)
    model1.addConstr(p_dis<=p_s_max*u_dis)
    model1.addConstr(soc[0,0] == soc_init*(1-theta)+yita*p_ch[0,0]/capmax-p_dis[0,0]/yita/capmax)
    for t in range(1,T):
      model1.addConstr(soc[0,t] == soc[0,t-1]*(1-theta)+p_ch[0,t]*yita/capmax-p_dis[0,t]/yita/capmax)
    model1.addConstr(u_ch+u_dis<=1)
    #model1.addConstr(u_ch+u_dis>=0)
    model1.addConstr(soc[0,23]==soc_init)
    #成本：维护成本
    c_ees = kees*gp.quicksum(p_ch[0,t].item()*yita+p_dis[0,t].item()/yita for t in range(T))
    
    #风光电：
    F = 12#保守性调节常量
    d_p_w_max = 0.4#箱式边界系数
    d_p_v_max = 0.4
    #变量：
    p_w = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="风电出力")
    p_v = model1.addMVar((1,T),vtype=GRB.CONTINUOUS,lb = 0,name="光电出力")
    
    u_w = uin["uw"]
    u_v = uin["uv"]
    print(f"u_w:\n{u_w}")
    print(f"u_v:\n{u_v}")
    print(f"pwf:\n{pw_f}")
    #约束：
    model1.addConstr(gp.quicksum(u_w[0,t] for t in range(T))<=F)
    model1.addConstr(gp.quicksum(u_v[0,t] for t in range(T))<=F)
    model1.addConstr(p_w == pw_f-u_w*d_p_w_max*pw_f)
    model1.addConstr(p_v == pv_f-u_v*d_p_v_max*pv_f)
    #成本:主要是弃风光惩罚
    c_wvt = 50*(pw_f-p_w)+50*(pv_f-p_v)
    c_wv=0
    for t in range(T):
      c_wv +=c_wvt[0,t]
    
    #负载模糊清晰化
    p_l_b = ((1 - alpha) * w_l[0] / 2+ w_l[1] / 2+ w_l[2] * alpha / 2) * pload
    print(f"plb:{p_l_b}")

    #电网：
    
    p_g_i=model1.addMVar((1, 24), vtype=GRB.CONTINUOUS)
    pgmaxsum=model1.addMVar((1, 24), vtype=GRB.CONTINUOUS)
    # 约束：
    for t in range(24):
        p_g_i_temp = gp.quicksum(p_g[n, t].item() for n in range(n_g))
        model1.addConstr(p_g_i[0,t]== p_g_i_temp)
    #model1.addConstr(p_l_b+p_ch-p_dis-p_w-p_v-p_h-p_g_i==0)
    model1.addConstr(p_l_b+p_ch-p_dis-p_buy+p_sell-p_w-p_v-p_g_i==0)
    
    for t in range(24):
        pgmaxsum_temp = gp.quicksum(u_g[n, t].item() * p_g_max[n] for n in range(n_g))
        model1.addConstr(pgmaxsum[0,t] == pgmaxsum_temp)
    model1.addConstr(p_l_b+p_ch-p_dis-p_buy+p_sell-p_w-p_v-pgmaxsum<=0)

    #碳排放配额补足交易,考虑使用二次项近似谈阶梯价格，然后再线性化，提升估算精度，单位为天
    EF_c_buy = model1.addMVar((1,24),vtype=GRB.CONTINUOUS,name = "碳排放补足量")
    u_efc_buy = model1.addMVar((1,24),vtype=GRB.BINARY,name = "碳市场补足状态")
    EF_c_sell = model1.addMVar((1,24),vtype=GRB.CONTINUOUS,name = "碳排放卖出量")
    u_efc_sell = model1.addMVar((1,24),vtype=GRB.BINARY,name = "碳市场卖出状态")
    #EF_c_2 = model1.addVar(vtype=GRB.CONTINUOUS,name = "碳排放补足量二次项")
    #lxefc2=np.linspace(start =0,stop=500,num=11).reshape(1,-1)
    #lyefc2 = lxefc2**2
    
    #model1.addGenConstrPWL(EF_c,EF_c_2 , lxefc2[0],lyefc2[0])
    model1.addConstr(EF_c_buy>=0)
    model1.addConstr(EF_c_buy<=efc_max*u_efc_buy)
    model1.addConstr(EF_c_sell>=0)
    model1.addConstr(EF_c_sell<=efc_max*u_efc_sell)
    model1.addConstr(u_efc_buy+u_efc_sell<=1)
    #碳排放约束，补足量使得碳排放量达到零碳园区的水平
    #EF = gp.quicksum((coef[0]-0.0246)*p_g_i[0,t]+(coef[1]-0.0246)*p_buy[0,t]-(coef[1]-0.0246)*p_sell[0,t]-0.0246*p_w[0,t]-0.0246*p_v[0,t]-EF_c[0,t]  for t in range(24))
    for t in range(T):
      EF = (coef[0]-0.0246)*p_g_i[0,t]+(coef[1]-0.0246)*p_buy[0,t]-(coef[1]-0.0246)*p_sell[0,t]-0.0246*p_w[0,t]-0.0246*p_v[0,t]-EF_c_buy[0,t]*u_efc_buy[0,t]+EF_c_sell[0,t]*u_efc_sell[0,t]

      model1.addConstr(EF==0)
    c_efc=gp.quicksum(EF_c_buy[0,t].item()-EF_c_sell[0,t].item() for t in range(24))
    '''
    ------------------------------------------------------------------
    '''
    C = model1.addVar(1,vtype=GRB.CONTINUOUS,name="成本c")
    model1.addConstr( C >=c_ees+c_g+c_wv+c_efc+c_m)
    '''
    -------------------------------------------------------------------
    '''
  model1.setParam(GRB.Param.OptimalityTol, 1e-8)
  model1.setParam(GRB.Param.FeasibilityTol, 1e-8) 
  model1.setObjective(C+c_u, GRB.MINIMIZE)
  model1.optimize()
  if model1.status != GRB.OPTIMAL:
      print("Model is infeasible. Computing IIS...")
      model1.computeIIS()
      model1.write("infeasible.ilp")
      print("IIS written to 'infeasible.ilp'")
  elif model1.status == GRB.UNBOUNDED:
      print("IIS written to 'infeasible.ilp'")
  else:
    U_start = u_start.X
    U_stop = u_stop.X
    U_g= u_g.X
    U_ch = u_ch.X
    U_dis = u_dis.X
    LB = model1.ObjVal
    np.set_printoptions(formatter={'float_kind': '{:.2f}'.format})
    print(f" 碳补足的量{EF_c_buy.X}\n{EF_c_sell.X}")
    rst ={ 
            "p_g":p_g.X,
            "p_buy":p_buy.X,
            "p_sell":p_sell.X,
            "p_ch":p_ch.X,
            "p_dis":p_dis.X,
            "soc":soc.X,
            "p_w":p_w.X,
            "p_v":p_v.X,
            "efcbuy":EF_c_buy.X,
            "efcsell":EF_c_sell.X,
            "ustart":U_start,
            "ustop":U_stop,
            "ug":U_g,
            "uch":U_ch,
            "udis":U_dis,
            "uefc_buy":u_efc_buy.X,
            "uefc_sell":u_efc_sell.X,
            "ubuy":u_buy.X,
            "usell":u_sell.X,
            "LB":LB,
            "C":C.X
    }
    return (rst)
